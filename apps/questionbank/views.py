from apps.common.views import BaseViewSet
from apps.questionbank.models import Chapter, Course, Question, QuestionResource, QuestionReview
from apps.questionbank.serializers import (
    ChapterSerializer,
    CourseSerializer,
    QuestionResourceSerializer,
    QuestionReviewSerializer,
    QuestionSerializer,
)


class CourseViewSet(BaseViewSet):
    """课程 CRUD。"""
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["id"]


class ChapterViewSet(BaseViewSet):
    """章节 CRUD。"""
    queryset = Chapter.objects.all()
    serializer_class = ChapterSerializer
    search_fields = ["name"]
    ordering_fields = ["id", "sort"]

    def get_queryset(self):
        qs = super().get_queryset()
        course = self.request.query_params.get("course")
        if course:
            qs = qs.filter(course_id=course)
        return qs


class QuestionViewSet(BaseViewSet):
    """试题 CRUD，支持按学科/章节/题型/难度/年级/状态过滤。"""
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    search_fields = ["stem"]
    ordering_fields = ["id", "difficulty", "score"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        filters = {
            "course": "course_id",
            "chapter": "chapter_id",
            "qtype": "qtype",
            "difficulty": "difficulty",
            "grade": "grade",
            "status": "status",
        }
        for param, field in filters.items():
            value = params.get(param)
            if value:
                qs = qs.filter(**{field: value})
        return qs


class QuestionResourceViewSet(BaseViewSet):
    """试题资源 CRUD。"""
    queryset = QuestionResource.objects.all()
    serializer_class = QuestionResourceSerializer


class QuestionReviewViewSet(BaseViewSet):
    """试题审核 CRUD。"""
    queryset = QuestionReview.objects.all()
    serializer_class = QuestionReviewSerializer
