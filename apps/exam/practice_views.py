"""学生练习测评（practice）。

学生自主练习：按学科随机组卷、创建练习答卷、查看练习记录与详情。
练习答卷的「保存进度 / 提交判分」复用 /api/exam/answer-sheets/ 下已有接口：
- PUT  /api/exam/answer-sheets/{id}/answers/   保存答题进度
- POST /api/exam/answer-sheets/{id}/submit/    提交并自动判分

接口清单：
1. POST /api/exam/practice/random/      按学科随机组卷并创建练习答卷
2. GET  /api/exam/practice/sheets/      我的练习记录（publish 为空的答卷）
3. GET  /api/exam/practice/{id}/sheets/ 练习详情（已提交才返回答案/解析与正确率统计）
"""
import random
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action

from apps.common.exceptions import ApiException
from apps.common.pagination import StandardPagination
from apps.common.permissions import has_role
from apps.common.response import ApiResponse, ErrorCode
from apps.exam import services
from apps.exam.models import AnswerSheet, Paper, PaperQuestion
from apps.questionbank.models import Course, Question
from apps.users.models import User

# 学科 → 课程名映射（与 views.py 中 PaperViewSet._resolve_course 保持一致）
SUBJECT_TO_COURSE_NAME = {
    Paper.SUBJECT_MUSIC: "音乐",
    Paper.SUBJECT_ART: "美术",
}

# 练习默认抽题配置：题型 × 数量（某题型不足时自动降级，有多少抽多少）
PRACTICE_QTYPE_CONFIG = [
    ("single", 5),
    ("multiple", 2),
    ("judge", 3),
    ("fill", 2),
]

# 未指定题量时的兜底抽取数量
DEFAULT_QUESTION_COUNT = 10


def _as_list(value):
    """把 list / JSON 字符串 / 逗号分隔字符串统一成字符串列表。"""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def _subject_questions(subject):
    """按学科代码聚合题目（同一学科可能拆成多条 code 相同的课程，如多个音乐课程 code 均为 music）。

    按 course.code 聚合而非取单个课程，避免 .first() 抽到题量为 0 或年级不匹配的那条。
    code 为空的历史课程退回按中文课程名匹配；两者都无课程时才抛 404。
    """
    qs = Question.objects.filter(course__code=subject, is_deleted=False)
    name = SUBJECT_TO_COURSE_NAME.get(subject)

    if not qs.exists() and name:
        course_ids = list(
            Course.objects.filter(name=name, is_deleted=False).values_list("id", flat=True)
        )
        if course_ids:
            qs = Question.objects.filter(course_id__in=course_ids, is_deleted=False)

    has_code_course = Course.objects.filter(code=subject, is_deleted=False).exists()
    has_name_course = bool(name) and Course.objects.filter(name=name, is_deleted=False).exists()
    if not has_code_course and not has_name_course:
        raise ApiException(f"未找到学科对应的课程：{subject}", code=ErrorCode.NOT_FOUND, status=404)

    return qs


def _random_sample(queryset, count):
    """用 Python random.sample 从 queryset 中真随机抽 count 条，比 order_by('?') 更可靠。"""
    ids = list(queryset.values_list("id", flat=True))
    if len(ids) <= count:
        random.shuffle(ids)
        return list(queryset.filter(id__in=ids))
    return list(queryset.filter(id__in=random.sample(ids, count)))


class PracticeViewSet(viewsets.GenericViewSet):
    """学生练习测评：随机组卷、练习记录、练习详情。"""

    permission_classes = [has_role(User.ROLE_STUDENT)]
    pagination_class = StandardPagination

    def _paper_payload(self, paper):
        return {
            "id": paper.id,
            "title": paper.title,
            "subject": paper.subject,
            "subject_display": paper.get_subject_display(),
            "ptype": paper.ptype,
            "ptype_display": paper.get_ptype_display(),
            "duration": paper.duration,
            "total_score": str(paper.total_score),
            "question_count": paper.paper_questions.count(),
        }

    @action(detail=False, methods=["post"], url_path="random")
    def random(self, request):
        """按学科随机组卷并创建练习答卷。

        body:
            {
              "subject": "music" | "art",          # 必填
              "question_count": 10,                # 选填，总题数
              "qtypes": ["single", "judge"],       # 选填，题型；数组或 "single,judge"
              "difficulties": ["easy", "medium"],  # 选填，难度；数组或逗号分隔
              "chapter_id": 3,                     # 选填，限定章节
              "grade": "三年级"                     # 选填；""/"all" 不限年级
            }
        返回: {sheet, paper, questions, meta}，HTTP 201。
        """
        subject = request.data.get("subject")
        if subject not in (Paper.SUBJECT_MUSIC, Paper.SUBJECT_ART):
            raise ApiException("subject 仅支持 music / art", code=ErrorCode.INVALID_PARAM, status=400)

        base_qs = _subject_questions(subject).filter(status=Question.STATUS_APPROVED)

        # ---- 题型 / 难度 / 章节 过滤 ----
        qtypes = _as_list(request.data.get("qtypes"))
        if qtypes:
            valid_types = {key for key, _ in Question.TYPE_CHOICES}
            invalid = [q for q in qtypes if q not in valid_types]
            if invalid:
                raise ApiException(
                    f"不支持的题型：{','.join(invalid)}", code=ErrorCode.INVALID_PARAM, status=400,
                )
            base_qs = base_qs.filter(qtype__in=qtypes)

        difficulties = _as_list(request.data.get("difficulties"))
        if difficulties:
            valid_diff = {key for key, _ in Question.DIFFICULTY_CHOICES}
            invalid = [d for d in difficulties if d not in valid_diff]
            if invalid:
                raise ApiException(
                    f"不支持的难度：{','.join(invalid)}", code=ErrorCode.INVALID_PARAM, status=400,
                )
            base_qs = base_qs.filter(difficulty__in=difficulties)

        chapter_id = request.data.get("chapter_id")
        if chapter_id:
            base_qs = base_qs.filter(chapter_id=chapter_id)

        # ---- 年级：未指定时沿用学生所在班级年级；显式传 ""/"all" 表示不限 ----
        if "grade" in request.data:
            grade = str(request.data.get("grade") or "").strip()
            if grade.lower() == "all":
                grade = ""
        else:
            grade = services.student_grade(request.user)

        # 年级逐级降级：班级年级精确过滤无题时，放弃年级条件以保底组卷
        grade_relaxed = False
        final_qs = base_qs
        if grade:
            grade_qs = base_qs.filter(grade=grade)
            if grade_qs.count() == 0:
                final_qs = base_qs
                grade_relaxed = True
            else:
                final_qs = grade_qs

        available_count = final_qs.count()
        if available_count == 0:
            qtype_label = "、".join(dict(Question.TYPE_CHOICES).get(q, q) for q in qtypes) or "全部"
            difficulty_label = "、".join(dict(Question.DIFFICULTY_CHOICES).get(d, d) for d in difficulties) or "全部"
            approved_total = _subject_questions(subject).filter(status=Question.STATUS_APPROVED).count()
            raise ApiException(
                f"题库中没有符合条件的试题（学科：{dict(Paper.SUBJECT_CHOICES)[subject]}；"
                f"题型：{qtype_label}；难度：{difficulty_label}；年级：{grade or '不限'}）；"
                f"该学科已通过试题共 {approved_total} 道",
                code=ErrorCode.INVALID_PARAM, status=400,
            )

        # ---- 抽题（改用 Python random.sample 真随机）----
        raw_count = request.data.get("question_count")
        try:
            question_count = int(raw_count) if raw_count not in (None, "") else 0
        except (TypeError, ValueError):
            raise ApiException("question_count 必须是整数", code=ErrorCode.INVALID_PARAM, status=400)

        if question_count > 0:
            picked = _random_sample(final_qs, question_count)
        elif qtypes:
            picked = _random_sample(final_qs, DEFAULT_QUESTION_COUNT)
        else:
            picked = []
            for qtype, count in PRACTICE_QTYPE_CONFIG:
                picked.extend(_random_sample(final_qs.filter(qtype=qtype), count))
            if not picked:
                picked = _random_sample(final_qs, DEFAULT_QUESTION_COUNT)

        random.shuffle(picked)

        total_score = sum((q.score for q in picked), Decimal("0"))
        subject_display = dict(Paper.SUBJECT_CHOICES)[subject]
        title = f"{subject_display}练习卷 · {timezone.now().strftime('%m%d%H%M%S')}"

        with transaction.atomic():
            paper = Paper.objects.create(
                title=title,
                ptype=Paper.TYPE_PRACTICE,
                subject=subject,
                level=Paper.LEVEL_CLASS,
                grade=grade,
                duration=0,
                total_score=total_score,
                status=Paper.STATUS_DRAFT,
                creator=request.user,
            )
            PaperQuestion.objects.bulk_create([
                PaperQuestion(paper=paper, question=q, sort=i + 1, score=q.score)
                for i, q in enumerate(picked)
            ])
            sheet = AnswerSheet.objects.create(
                paper=paper,
                student=request.user,
                started_at=timezone.now(),
            )

        links = (
            paper.paper_questions.select_related("question")
            .prefetch_related("question__resources")
            .order_by("sort")
        )
        data = {
            "sheet": services.sheet_payload(sheet),
            "paper": self._paper_payload(paper),
            "questions": [services.question_payload(link, request) for link in links],
            "meta": {
                "requested_count": question_count,
                "picked_count": len(picked),
                "available_count": available_count,
                "shortage": max(0, question_count - len(picked)) if question_count else 0,
                "qtypes": qtypes,
                "difficulties": difficulties,
                "grade": grade,
                "grade_relaxed": grade_relaxed,
            },
        }
        return ApiResponse(data=data, message="组卷成功", status=201)

    @action(detail=False, methods=["get"], url_path="sheets", url_name="sheet-list")
    def sheet_list(self, request):
        """我的练习记录（publish 为空的答卷，即练习卷）。"""
        sheets = (
            AnswerSheet.objects.filter(
                student=request.user,
                publish__isnull=True,
                paper__ptype=Paper.TYPE_PRACTICE,
            )
            .select_related("paper")
            .order_by("-created_at")
        )
        items = [
            {
                "sheet_id": s.id,
                "paper_id": s.paper_id,
                "title": s.paper.title,
                "subject": s.paper.subject,
                "subject_display": s.paper.get_subject_display(),
                "ptype": s.paper.ptype,
                "ptype_display": s.paper.get_ptype_display(),
                "total_score": str(s.paper.total_score),
                "question_count": s.paper.paper_questions.count(),
                "my_score": str(s.total_score) if s.is_submitted else None,
                "is_submitted": s.is_submitted,
                "started_at": s.started_at,
                "submitted_at": s.submitted_at,
            }
            for s in sheets
        ]
        page = self.paginate_queryset(items)
        return self.get_paginated_response(page)

    @action(detail=True, methods=["get"], url_path="sheets", url_name="sheet-detail")
    def sheet_detail(self, request, pk=None):
        """练习详情：已提交才返回答案/解析、逐题作答结果与正确率统计。"""
        sheet = (
            AnswerSheet.objects.filter(
                pk=pk,
                student=request.user,
                publish__isnull=True,
                paper__ptype=Paper.TYPE_PRACTICE,
            )
            .select_related("paper")
            .first()
        )
        if sheet is None:
            raise ApiException("练习答卷不存在", code=ErrorCode.NOT_FOUND, status=404)

        submitted = sheet.is_submitted
        paper = sheet.paper
        links = list(
            paper.paper_questions.select_related("question")
            .prefetch_related("question__resources")
            .order_by("sort")
        )
        answers = {a.question_id: a for a in sheet.answers.all()}

        questions = []
        for link in links:
            payload = services.question_payload(link, request, show_answer=submitted)
            if submitted:
                answer = answers.get(link.question_id)
                payload["my_answer"] = answer.answer if answer else ""
                payload["my_score"] = str(answer.score) if answer else "0.00"
                payload["is_correct"] = answer.is_correct if answer else None
            questions.append(payload)

        data = {
            "sheet": services.sheet_payload(sheet),
            "paper": self._paper_payload(paper),
            "questions": questions,
        }

        if submitted:
            correct = wrong = subjective = 0
            for link in links:
                answer = answers.get(link.question_id)
                if answer and answer.is_correct is True:
                    correct += 1
                elif answer and answer.is_correct is False:
                    wrong += 1
                else:
                    subjective += 1

            total_full = paper.total_score or Decimal("0")
            my_score = sheet.total_score or Decimal("0")
            ratio = float(my_score) / float(total_full) if float(total_full) > 0 else 0
            data["stats"] = {
                "my_score": str(my_score),
                "total_score": str(total_full),
                "correct_rate": round(correct / len(links), 4) if links else 0,
                "score_rate": round(ratio, 4),
                "correct_count": correct,
                "wrong_count": wrong,
                "subjective_count": subjective,
            }

        return ApiResponse(data=data)
