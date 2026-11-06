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
from django.db.models import Q
from django.http import StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.decorators import action

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


class PaperViewSet(BaseViewSet):
    """试卷 CRUD，含自动组卷与暂存。"""
    queryset = Paper.objects.all()
    serializer_class = PaperSerializer
    permission_classes = [has_role(*PAPER_ROLES)]
    search_fields = ["title"]
    ordering_fields = ["id"]

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
                qs = qs.filter(**{field: value})
        return qs

    @staticmethod
    def _resolve_course(subject):
        """把 Paper.subject（music/art）映射到 questionbank.Course。"""
        course = Course.objects.filter(code=subject).first()
        if course is None:
            name = SUBJECT_TO_COURSE_NAME.get(subject)
            course = Course.objects.filter(name=name).first() if name else None
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

        qtype_label_map = dict(Question.TYPE_CHOICES)
        difficulty_label_map = dict(Question.DIFFICULTY_CHOICES)

        picked = []
        for cfg in qtype_config:
            qtype = cfg["qtype"]
            difficulty = cfg["difficulty"]
            count = cfg["count"]
            qs = base_qs.filter(qtype=qtype, difficulty=difficulty)
            available = qs.count()
            if available < count:
                raise ApiException(
                    f"{qtype_label_map.get(qtype, qtype)}题型"
                    f"{difficulty_label_map.get(difficulty, difficulty)}难度仅找到{available}道题",
                    code=ErrorCode.INVALID_PARAM,
                    status=400,
                )
            picked.extend(qs.order_by("?")[:count])

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

        return ApiResponse(PaperDetailSerializer(paper).data, message="自动组卷成功", status=201)

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


class FunContentViewSet(BaseViewSet):
    """趣味课堂：省级发布管理，学生按发布范围可见。"""

    queryset = FunContent.objects.all()
    serializer_class = FunContentSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [has_role(User.ROLE_STUDENT, User.ROLE_PROVINCE)()]
        return [has_role(User.ROLE_PROVINCE)()]

    def get_queryset(self):
        qs = super().get_queryset().select_related("creator", "school", "target_class")
        user = self.request.user
        if user.role == User.ROLE_STUDENT:
            # 越权保护：仅已发布，且学校/班级匹配本人
            class_ids = services.student_class_ids(user)
            qs = qs.filter(
                Q(school__isnull=True) | Q(school_id=user.school_id),
                Q(target_class__isnull=True) | Q(target_class_id__in=class_ids),
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

    def perform_create(self, serializer):
        """creator / school 由后端注入，省级发布不绑定学校。"""
        user = self.request.user
        extra = {"creator": user, "school": user.school if user.school_id else None}
        # 创建即发布时补齐发布时间
        if serializer.validated_data.get("status") == FunContent.STATUS_PUBLISHED:
            extra["published_at"] = timezone.now()
        serializer.save(**extra)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        """发布：学生端可见。"""
        content = self.get_object()
        content.status = FunContent.STATUS_PUBLISHED
        content.published_at = timezone.now()
        content.save(update_fields=["status", "published_at", "updated_at"])
        return ApiResponse(self.get_serializer(content).data, message="发布成功")

    @action(detail=True, methods=["post"])
    def recall(self, request, pk=None):
        """撤回：学生端不可见。"""
        content = self.get_object()
        content.status = FunContent.STATUS_DRAFT
        content.published_at = None
        content.save(update_fields=["status", "published_at", "updated_at"])
        return ApiResponse(self.get_serializer(content).data, message="已撤回")
