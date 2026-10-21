from rest_framework.decorators import action

from apps.common.claude_service import get_claude_service
from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse
from apps.common.views import BaseViewSet
from apps.exam.models import Answer, Paper, PaperPublish, PaperQuestion
from apps.exam.serializers import (
    AnswerSerializer,
    PaperPublishSerializer,
    PaperQuestionSerializer,
    PaperSerializer,
)
from apps.questionbank.models import Question
from apps.users.models import User


class PaperViewSet(BaseViewSet):
    """试卷 CRUD。"""
    queryset = Paper.objects.all()
    serializer_class = PaperSerializer
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


class PaperQuestionViewSet(BaseViewSet):
    """试卷试题关联。"""
    queryset = PaperQuestion.objects.all()
    serializer_class = PaperQuestionSerializer


class PaperPublishViewSet(BaseViewSet):
    """试卷发布。"""
    queryset = PaperPublish.objects.all()
    serializer_class = PaperPublishSerializer


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
        """对指定答题记录进行 AI 评分（调用 Claude）。

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

        result = get_claude_service().grade_answer(
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
                r = get_claude_service().grade_answer(
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
