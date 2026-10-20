"""测评：试卷、发布、答卷、成绩、证书。"""
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from rest_framework.decorators import action

from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse, ErrorCode
from apps.common.views import BaseViewSet
from apps.exam.models import Answer, AnswerSheet, Certificate, Paper, PaperPublish, PaperQuestion
from apps.exam.serializers import (
    AnswerSerializer,
    AnswerSheetSerializer,
    AutoGenerateRequestSerializer,
    CertificateSerializer,
    DraftRequestSerializer,
    PaperDetailSerializer,
    PaperPublishSerializer,
    PaperQuestionSerializer,
    PaperSerializer,
)
from apps.questionbank.models import Course, Question
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

    @action(detail=True, methods=["post"], url_path="draft")
    def draft(self, request, pk=None):
        """暂存试卷：按传入顺序重建试题关联，并置为草稿。"""
        paper = self.get_object()
        serializer = DraftRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question_ids = serializer.validated_data["question_ids"]

        if len(set(question_ids)) != len(question_ids):
            raise ApiException("question_ids 存在重复", code=ErrorCode.INVALID_PARAM, status=400)

        id_to_question = {q.id: q for q in Question.objects.filter(id__in=question_ids)}
        if len(id_to_question) != len(question_ids):
            raise ApiException("部分试题不存在", code=ErrorCode.INVALID_PARAM, status=400)
        ordered = [id_to_question[qid] for qid in question_ids]

        total_score = sum((q.score for q in ordered), Decimal("0"))

        with transaction.atomic():
            paper.paper_questions.all().delete()
            PaperQuestion.objects.bulk_create([
                PaperQuestion(paper=paper, question=q, sort=i + 1, score=q.score)
                for i, q in enumerate(ordered)
            ])
            paper.status = Paper.STATUS_DRAFT
            paper.total_score = total_score
            paper.save(update_fields=["status", "total_score"])

        return ApiResponse(PaperDetailSerializer(paper).data, message="暂存成功")


class PaperQuestionViewSet(BaseViewSet):
    """试卷试题关联。"""
    queryset = PaperQuestion.objects.all()
    serializer_class = PaperQuestionSerializer


class PaperPublishViewSet(BaseViewSet):
    """试卷发布。"""
    queryset = PaperPublish.objects.all()
    serializer_class = PaperPublishSerializer


class AnswerSheetViewSet(BaseViewSet):
    """答卷。"""
    queryset = AnswerSheet.objects.all()
    serializer_class = AnswerSheetSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        student = self.request.query_params.get("student")
        if student:
            qs = qs.filter(student_id=student)
        return qs


class AnswerViewSet(BaseViewSet):
    """答题明细。"""
    queryset = Answer.objects.all()
    serializer_class = AnswerSerializer


class CertificateViewSet(BaseViewSet):
    """证书。"""
    queryset = Certificate.objects.all()
    serializer_class = CertificateSerializer
