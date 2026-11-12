from rest_framework.decorators import action

from apps.common.deepseek_service import get_deepseek_service
from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse
"""测评：试卷、发布、答卷、成绩、证书。"""
import io
import os
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import quote

from django.db import transaction
from django.db.models import Count, Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.classroom.models import ClassRoom

from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse, ErrorCode
from apps.common.views import BaseViewSet
from apps.exam import services
from apps.exam.models import Answer, FunContent, Paper, PaperPublish, PaperQuestion
from apps.exam.serializers import (
    AnswerSerializer,
    AnswerSheetSerializer,
    AutoGenerateRequestSerializer,
    CertificateSerializer,
    DraftRequestSerializer,
    FunContentSerializer,
    PaperDetailSerializer,
    PaperPublishSerializer,
    PaperQuestionSerializer,
    PaperSerializer,
    PublishCreateSerializer,
)
from apps.questionbank.models import Question
from apps.users.models import User
from apps.questionbank.models import Course, Question, QuestionResource
from apps.users.models import User


PAPER_ROLES = (
    User.ROLE_TEACHER,
    User.ROLE_SCHOOL,
    User.ROLE_DISTRICT,
    User.ROLE_CITY,
    User.ROLE_PROVINCE,
)

SUBJECT_TO_COURSE_NAME = {
    Paper.SUBJECT_MUSIC: "音乐",
    Paper.SUBJECT_ART: "美术",
}

SUBJECT_ALIASES = {
    Paper.SUBJECT_MUSIC: Paper.SUBJECT_MUSIC,
    Paper.SUBJECT_ART: Paper.SUBJECT_ART,
    "音乐": Paper.SUBJECT_MUSIC,
    "美术": Paper.SUBJECT_ART,
}

GRADE_OPTIONS = ("一年级", "二年级", "三年级", "四年级", "五年级", "六年级")


def normalize_subject(value):
    """把前端可能传来的学科代码/中文名/课程 ID 统一为 Paper.subject 代码。"""
    raw = str(value).strip()
    if raw in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[raw]
    course = Course.objects.filter(id=raw).first() if raw.isdigit() else None
    if course is None:
        course = Course.objects.filter(name=raw).first()
    if course is not None:
        if course.code in SUBJECT_ALIASES:
            return SUBJECT_ALIASES[course.code]
        if course.name in SUBJECT_ALIASES:
            return SUBJECT_ALIASES[course.name]
    return raw


class PaperViewSet(BaseViewSet):
    """试卷 CRUD，含自动组卷与暂存。"""
    queryset = Paper.objects.all()
    serializer_class = PaperSerializer
    permission_classes = [has_role(*PAPER_ROLES)]
    search_fields = ["title"]
    ordering_fields = ["id"]

    def get_serializer_class(self):
        """详情返回含嵌套题目的 PaperDetailSerializer，列表保持轻量。"""
        if self.action == "retrieve":
            return PaperDetailSerializer
        return PaperSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        for param, field in {
            "subject": "subject",
            "ptype": "ptype",
            "level": "level",
            "grade": "grade",
            "status": "status",
        }.items():
            value = params.get(param)
            if value:
                if field == "subject":
                    value = normalize_subject(value)
                qs = qs.filter(**{field: value})
        return qs

    @staticmethod
    def _resolve_course(subject):
        """把 Paper.subject（music/art）映射到 questionbank.Course。

        题库中同一学科可能有多条课程记录（如 code 均为 music 的「音乐鉴赏」「音乐」），
        因此优先按中文名精确匹配，其次退回 code 匹配，并取题量最多的一条，
        避免抽到只有零星题目的同 code 课程。
        """
        name = SUBJECT_TO_COURSE_NAME.get(subject)
        candidates = Course.objects.none()
        if name:
            candidates = Course.objects.filter(name=name, is_deleted=False)
        if not candidates.exists():
            candidates = Course.objects.filter(code=subject, is_deleted=False)
        course = candidates.annotate(_question_count=Count("questions")).order_by(
            "-_question_count", "id",
        ).first()
        if course is None:
            raise ApiException(f"未找到学科对应的课程：{subject}", code=ErrorCode.NOT_FOUND, status=404)
        return course

    @staticmethod
    def _split_scores(questions, total_score):
        """按各题原始分值比例分配 total_score；原始分全为 0 时等分。"""
        total = Decimal(str(total_score))
        orig_total = sum((q.score or 0 for q in questions), Decimal("0"))
        if orig_total > 0:
            scores = [
                (total * (q.score or 0) / orig_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                for q in questions
            ]
        else:
            base = (total / len(questions)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            scores = [base] * len(questions)
        # 最后一题吸收舍入误差，保证合计恰等于 total_score
        scores[-1] = total - sum(scores[:-1])
        return scores

    @extend_schema(
        request=AutoGenerateRequestSerializer,
        responses={201: PaperDetailSerializer},
    )
    @action(detail=False, methods=["post"], url_path="auto-generate")
    def auto_generate(self, request):
        """自动组卷：按学科/年级/章节/题型配置，从已通过题库随机抽题。"""
        serializer = AutoGenerateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        subject = data["subject"]
        grade = data.get("grade", "")
        chapter_ids = data.get("chapter_ids") or []
        qtype_config = data["qtype_config"]
        title = data["title"]
        ptype = data.get("ptype", Paper.TYPE_PRACTICE)
        level = data.get("level", Paper.LEVEL_CLASS)
        total_score = data.get("total_score")

        course = self._resolve_course(subject)

        base_qs = Question.objects.filter(course=course, status=Question.STATUS_APPROVED)
        if grade:
            base_qs = base_qs.filter(grade=grade)
        if chapter_ids:
            base_qs = base_qs.filter(chapter_id__in=chapter_ids)

        difficulty_order = [key for key, _ in Question.DIFFICULTY_CHOICES]
        target = sum(cfg["count"] for cfg in qtype_config)

        picked = []
        picked_ids = set()
        relaxed = False

        def take(qs, limit):
            """从 qs 随机取至多 limit 道，并在整卷范围内去重。"""
            if limit <= 0:
                return []
            rows = list(qs.exclude(id__in=picked_ids).order_by("?")[:limit])
            picked_ids.update(q.id for q in rows)
            return rows

        # 跨年级候选池：仍限定同学科与已选章节范围
        cross_grade_qs = Question.objects.filter(
            course=course, status=Question.STATUS_APPROVED,
        )
        if chapter_ids:
            cross_grade_qs = cross_grade_qs.filter(chapter_id__in=chapter_ids)

        for cfg in qtype_config:
            qtype = cfg["qtype"]
            difficulty = cfg["difficulty"]
            count = cfg["count"]

            # 1) 严格匹配：同年级 + 同题型 + 同难度
            grade_qs = base_qs.filter(qtype=qtype)
            selected = take(grade_qs.filter(difficulty=difficulty), count)

            # 2) 同年级内放宽难度，难度最接近的优先
            if len(selected) < count:
                offset = difficulty_order.index(difficulty)
                for other in sorted(
                    (d for d in difficulty_order if d != difficulty),
                    key=lambda d: abs(difficulty_order.index(d) - offset),
                ):
                    if len(selected) >= count:
                        break
                    extra = take(grade_qs.filter(difficulty=other), count - len(selected))
                    if extra:
                        relaxed = True
                        selected.extend(extra)

            # 3) 仍不足时跨年级补足（同题型）
            if len(selected) < count and grade:
                extra = take(cross_grade_qs.filter(qtype=qtype), count - len(selected))
                if extra:
                    relaxed = True
                    selected.extend(extra)

            picked.extend(selected)

        # 4) 兜底：同年级任意题型补足，最后再放宽到同学科其他年级
        if len(picked) < target:
            extra = take(base_qs, target - len(picked))
            if extra:
                relaxed = True
                picked.extend(extra)
        if len(picked) < target and grade:
            extra = take(cross_grade_qs, target - len(picked))
            if extra:
                relaxed = True
                picked.extend(extra)

        if len(picked) < target:
            raise ApiException(
                f"题库题量不足：本次组卷需{target}道题，当前题库仅有{len(picked)}道，请先补充题库",
                code=ErrorCode.INVALID_PARAM,
                status=400,
            )

        if total_score is None:
            scores = [q.score for q in picked]
            total_score = sum(scores, Decimal("0"))
        else:
            scores = self._split_scores(picked, total_score)
            total_score = Decimal(str(total_score))

        with transaction.atomic():
            paper = Paper.objects.create(
                title=title,
                ptype=ptype,
                subject=subject,
                level=level,
                grade=grade,
                total_score=total_score,
                status=Paper.STATUS_DRAFT,
                creator=request.user,
            )
            PaperQuestion.objects.bulk_create([
                PaperQuestion(paper=paper, question=q, sort=i + 1, score=scores[i])
                for i, q in enumerate(picked)
            ])

        message = "自动组卷成功"
        if relaxed:
            message = "自动组卷成功，部分题目因题库数量不足已按相近难度或年级补足"
        return ApiResponse(PaperDetailSerializer(paper).data, message=message, status=201)

    @extend_schema(
        request=DraftRequestSerializer,
        responses={200: PaperDetailSerializer},
    )
    @action(detail=True, methods=["post"], url_path="draft")
    def draft(self, request, pk=None):
        """暂存试卷：按传入顺序重建试题关联，并置为草稿。

        兼容两种请求格式：
        - 新版 questions：逐题指定分值，[{"question_id": 101, "score": 5}]；
        - 旧版 question_ids：[101, 205]，沿用题目默认分值。
        两者同时传入时优先使用 questions。
        """
        paper = self.get_object()
        serializer = DraftRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        questions = data.get("questions")
        if questions:
            # 新版：逐题分值
            question_ids = [item["question_id"] for item in questions]
            score_map = {item["question_id"]: item["score"] for item in questions}
        else:
            # 旧版：题目 ID 数组，沿用题目默认分值
            question_ids = data["question_ids"]
            score_map = None

        if len(set(question_ids)) != len(question_ids):
            raise ApiException("题目 ID 存在重复", code=ErrorCode.INVALID_PARAM, status=400)

        id_to_question = {q.id: q for q in Question.objects.filter(id__in=question_ids)}
        if len(id_to_question) != len(question_ids):
            raise ApiException("部分试题不存在", code=ErrorCode.INVALID_PARAM, status=400)
        ordered = [id_to_question[qid] for qid in question_ids]

        scores = [score_map[qid] for qid in question_ids] if score_map is not None else [q.score for q in ordered]
        total_score = sum(scores, Decimal("0"))

        with transaction.atomic():
            paper.paper_questions.all().delete()
            PaperQuestion.objects.bulk_create([
                PaperQuestion(paper=paper, question=q, sort=i + 1, score=scores[i])
                for i, q in enumerate(ordered)
            ])
            paper.status = Paper.STATUS_DRAFT
            paper.total_score = total_score
            paper.save(update_fields=["status", "total_score"])

        return ApiResponse(PaperDetailSerializer(paper).data, message="暂存成功")

    @extend_schema(
        responses={(200, "application/zip"): OpenApiTypes.BINARY},
    )
    @action(detail=True, methods=["get"], url_path="materials")
    def materials(self, request, pk=None):
        """下载试卷音频/图片材料（内存 zip 打包）。"""
        paper = self.get_object()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            paper_questions = paper.paper_questions.select_related(
                "question",
            ).prefetch_related("question__resources").order_by("sort")
            for pq in paper_questions:
                question = pq.question
                for res in question.resources.all():
                    if res.rtype not in (
                        QuestionResource.RESOURCE_AUDIO,
                        QuestionResource.RESOURCE_IMAGE,
                    ):
                        continue
                    base = os.path.basename(res.file.name) or "file"
                    arcname = f"{pq.sort:03d}_{res.rtype}_{base}"
                    with res.file.open("rb") as fh:
                        zf.writestr(arcname, fh.read())

        filename = f"{paper.title}_材料.zip"
        response = StreamingHttpResponse(iter([buf.getvalue()]), content_type="application/zip")
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return response

    @extend_schema(
        responses={(200, "text/plain"): OpenApiTypes.STR},
    )
    @action(detail=True, methods=["get"], url_path="answers")
    def answers(self, request, pk=None):
        """下载试卷答案（纯文本 .txt）。"""
        paper = self.get_object()

        lines = [f"试卷：{paper.title}", f"学科：{paper.get_subject_display()}", ""]
        paper_questions = paper.paper_questions.select_related("question").order_by("sort")
        for pq in paper_questions:
            question = pq.question
            qtype_label = dict(Question.TYPE_CHOICES).get(question.qtype, question.qtype)
            lines.append(f"{pq.sort}. 【{qtype_label}】{question.stem}")
            lines.append(f"参考答案：{question.answer or '（无）'}")
            if question.analysis:
                lines.append(f"解析：{question.analysis}")
            lines.append("")

        content = "\n".join(lines)
        filename = f"{paper.title}_答案.txt"
        response = StreamingHttpResponse(
            iter([content.encode("utf-8")]), content_type="text/plain; charset=utf-8",
        )
        response["Content-Disposition"] = f"attachment; filename*=UTF-8''{quote(filename)}"
        return response


class PaperQuestionViewSet(BaseViewSet):
    """试卷试题关联。"""
    queryset = PaperQuestion.objects.all()
    serializer_class = PaperQuestionSerializer


class PaperPublishViewSet(BaseViewSet):
    """试卷发布（含 scope 参数化发布与撤回）。"""
    queryset = PaperPublish.objects.all()
    serializer_class = PaperPublishSerializer
    permission_classes = [has_role(*PAPER_ROLES)]

    @extend_schema(
        request=PublishCreateSerializer,
        responses={201: PaperPublishSerializer},
    )
    def create(self, request, *args, **kwargs):
        """发布试卷：校验 scope 后创建发布记录，并把 Paper 置为 published。"""
        serializer = PublishCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        paper = data["paper"]

        with transaction.atomic():
            publish = PaperPublish.objects.create(
                paper=paper,
                scope_type=data["scope_type"],
                grade=data.get("grade", ""),
                target_school=data.get("target_school"),
                target_class=data.get("target_class"),
                target_region=data.get("target_region"),
                start_at=data.get("start_at"),
                end_at=data.get("end_at"),
                status=PaperPublish.STATUS_PUBLISHED,
            )
            paper.status = Paper.STATUS_PUBLISHED
            paper.save(update_fields=["status"])

        return ApiResponse(PaperPublishSerializer(publish).data, message="发布成功", status=201)

    @extend_schema(
        responses={200: PaperPublishSerializer},
    )
    @action(detail=True, methods=["post"], url_path="recall")
    def recall(self, request, pk=None):
        """撤回发布：若无其它已发布记录，Paper 置回 draft。"""
        publish = self.get_object()
        with transaction.atomic():
            publish.status = PaperPublish.STATUS_RECALLED
            publish.save(update_fields=["status"])
            paper = publish.paper
            if not paper.publishes.filter(status=PaperPublish.STATUS_PUBLISHED).exists():
                paper.status = Paper.STATUS_DRAFT
                paper.save(update_fields=["status"])
        return ApiResponse(PaperPublishSerializer(publish).data, message="撤回成功")


class AnswerViewSet(BaseViewSet):
    """答题明细。"""
    queryset = Answer.objects.all()
    serializer_class = AnswerSerializer

    @action(
        detail=True,
        methods=["post"],
        url_path="ai-grade",
        permission_classes=[has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)],
    )
    def ai_grade(self, request, pk=None):
        """对指定答题记录进行 AI 评分（调用 DeepSeek）。

        POST /api/exam/answers/{id}/ai-grade/
        可选 body: { "save": true }  — 是否把评分写回数据库（默认 true）
        权限：教师 / 学校管理员
        """
        answer: Answer = self.get_object()
        question: Question = answer.question

        # 仅对主观题进行 AI 评分
        subjective_types = {"short", "listening", "sight"}
        if question.qtype not in subjective_types:
            raise ApiException(
                f"题型 {question.get_qtype_display()} 非主观题，跳过 AI 评分",
                status=400,
            )

        if not answer.answer.strip():
            raise ApiException("学生未作答，无法评分", status=400)

        result = get_deepseek_service().grade_answer(
            question_content=question.stem,
            reference_answer=question.answer,
            student_answer=answer.answer,
            max_score=float(question.score),
        )

        save = request.data.get("save", True)
        if save:
            answer.score = result.score
            answer.is_correct = result.score >= float(question.score) * 0.6  # 60% 及格线
            answer.save(update_fields=["score", "is_correct", "updated_at"])

        return ApiResponse(data={
            "answer_id": answer.id,
            "score": result.score,
            "max_score": float(question.score),
            "feedback": result.feedback,
            "suggestions": result.suggestions,
            "saved": bool(save),
        })

    @action(
        detail=False,
        methods=["post"],
        url_path="ai-grade-batch",
        permission_classes=[has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)],
    )
    def ai_grade_batch(self, request):
        """批量 AI 评分（按答卷 ID）。

        POST /api/exam/answers/ai-grade-batch/
        body: { "sheet_id": 123, "save": true }
        权限：教师 / 学校管理员
        """
        sheet_id = request.data.get("sheet_id")
        if not sheet_id:
            raise ApiException("缺少 sheet_id 参数", status=400)

        answers = self.queryset.filter(sheet_id=sheet_id).select_related("question")
        save = request.data.get("save", True)
        subjective_types = {"short", "listening", "sight"}

        results = []
        for ans in answers:
            q: Question = ans.question
            if q.qtype not in subjective_types:
                results.append({"answer_id": ans.id, "skipped": True, "reason": "非主观题"})
                continue
            if not ans.answer.strip():
                results.append({"answer_id": ans.id, "skipped": True, "reason": "未作答"})
                continue
            try:
                r = get_deepseek_service().grade_answer(
                    question_content=q.stem,
                    reference_answer=q.answer,
                    student_answer=ans.answer,
                    max_score=float(q.score),
                )
                if save:
                    ans.score = r.score
                    ans.is_correct = r.score >= float(q.score) * 0.6
                    ans.save(update_fields=["score", "is_correct", "updated_at"])
                results.append({
                    "answer_id": ans.id,
                    "score": r.score,
                    "max_score": float(q.score),
                    "feedback": r.feedback,
                })
            except ApiException as exc:
                results.append({"answer_id": ans.id, "error": str(exc)})

        return ApiResponse(data={
            "sheet_id": sheet_id,
            "save": bool(save),
            "results": results,
            "total": len(results),
        })


if user.role == User.ROLE_STUDENT:
    # 越权保护：仅已发布，且学校/班级匹配本人
    class_ids = services.student_class_ids(user)
    qs = qs.filter(
        Q(school_isnull=True) | Q(school_id=user.school_id),
        Q(target_class_isnull=True) | Q(target_class_id__in=class_ids),
        status=FunContent.STATUS_PUBLISHED,
    )
return qs

def list(self, request, *args, **kwargs):
    """列表：支持 subject / status / category / keyword 筛选并分页。"""
    qs = self.get_queryset()
    params = request.query_params

    subject = params.get("subject")
    if subject:
        qs = qs.filter(subject=subject)
    # 学生只能看已发布内容，忽略 status 参数
    status = params.get("status")
    if status and request.user.role != User.ROLE_STUDENT:
        qs = qs.filter(status=status)
    category = params.get("category")
    if category:
        qs = qs.filter(category=category)
    keyword = (params.get("keyword") or "").strip()
    if keyword:
        qs = qs.filter(Q(title__icontains=keyword) | Q(summary__icontains=keyword))

    qs = qs.order_by("-published_at", "-created_at")
    page = self.paginate_queryset(qs)
    serializer = self.get_serializer(page, many=True)
    return self.get_paginated_response(serializer.data)
