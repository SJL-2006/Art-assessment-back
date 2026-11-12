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


def resolve_course(subject):
    """把 Paper.subject（music/art）映射到 questionbank.Course。"""
    course = Course.objects.filter(code=subject).first()
    if course is None:
        name = SUBJECT_TO_COURSE_NAME.get(subject)
        course = Course.objects.filter(name=name).first() if name else None
    if course is None:
        raise ApiException(f"未找到学科对应的课程：{subject}", code=ErrorCode.NOT_FOUND, status=404)
    return course


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

        body: {"subject": "music" | "art"}
        返回: {sheet, paper, questions}，HTTP 201。
        """
        subject = request.data.get("subject")
        if subject not in (Paper.SUBJECT_MUSIC, Paper.SUBJECT_ART):
            raise ApiException("subject 仅支持 music / art", code=ErrorCode.INVALID_PARAM, status=400)

        course = resolve_course(subject)
        base_qs = Question.objects.filter(course=course, status=Question.STATUS_APPROVED)

        # 学生有已通过审核的班级且班级填了年级 → 按该年级抽题；否则不限年级
        grade = services.student_grade(request.user)
        if grade:
            base_qs = base_qs.filter(grade=grade)

        picked = []
        for qtype, count in PRACTICE_QTYPE_CONFIG:
            picked.extend(base_qs.filter(qtype=qtype).order_by("?")[:count])

        if not picked:
            raise ApiException("题库暂无该学科试题，无法组卷", code=ErrorCode.INVALID_PARAM, status=400)

        total_score = sum((q.score for q in picked), Decimal("0"))
        subject_display = dict(Paper.SUBJECT_CHOICES)[subject]
        title = f"{subject_display}练习卷 · {timezone.now().strftime('%m%d%H%M')}"

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
