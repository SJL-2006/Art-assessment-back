from apps.common.views import BaseViewSet
from apps.exam.models import Answer, AnswerSheet, Certificate, Paper, PaperPublish, PaperQuestion
from apps.exam.serializers import (
    AnswerSerializer,
    AnswerSheetSerializer,
    CertificateSerializer,
    PaperPublishSerializer,
    PaperQuestionSerializer,
    PaperSerializer,
)


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
