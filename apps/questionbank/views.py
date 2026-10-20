"""题库：课程、章节、试题及其嵌套资源与审核接口。"""
from rest_framework.decorators import action

from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse, ErrorCode
from apps.common.views import BaseViewSet
from apps.questionbank.models import Chapter, Course, Question, QuestionResource, QuestionReview
from apps.questionbank.serializers import (
    ChapterSerializer,
    CourseSerializer,
    QuestionResourceSerializer,
    QuestionReviewSerializer,
    QuestionSerializer,
    ReviewRequestSerializer,
)
from apps.users.models import User


class CourseViewSet(BaseViewSet):
    """课程 CRUD。"""
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["id"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [has_role(User.ROLE_STUDENT, User.ROLE_TEACHER, User.ROLE_QB_ADMIN)()]
        return [has_role(User.ROLE_QB_ADMIN)()]


class ChapterViewSet(BaseViewSet):
    """章节 CRUD。"""
    queryset = Chapter.objects.all()
    serializer_class = ChapterSerializer
    search_fields = ["name"]
    ordering_fields = ["id", "sort"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [has_role(User.ROLE_STUDENT, User.ROLE_TEACHER, User.ROLE_QB_ADMIN)()]
        return [has_role(User.ROLE_QB_ADMIN)()]

    def get_queryset(self):
        qs = super().get_queryset()
        course = self.request.query_params.get("course")
        if course:
            qs = qs.filter(course_id=course)
        return qs


class QuestionViewSet(BaseViewSet):
    """试题 CRUD 及嵌套资源/审核接口。"""
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    search_fields = ["stem"]
    ordering_fields = ["id", "difficulty", "score"]

    def get_permissions(self):
        if self.action in ("review_question", "list_reviews"):
            return [has_role(User.ROLE_QB_ADMIN)()]
        return [has_role(User.ROLE_TEACHER, User.ROLE_QB_ADMIN)()]

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

    @action(detail=True, methods=["post"], url_path="resources")
    def upload_resource(self, request, pk=None):
        """上传试题资源（音频/图片/视频）。"""
        question = self.get_object()
        serializer = QuestionResourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(question=question)
        return ApiResponse(serializer.data, message="资源上传成功", status=201)

    def delete_resource(self, request, pk=None, rid=None):
        """删除指定试题资源。"""
        question = self.get_object()
        try:
            resource = question.resources.get(pk=rid)
        except QuestionResource.DoesNotExist:
            raise ApiException("资源不存在", code=ErrorCode.NOT_FOUND, status=404)
        resource.delete()
        return ApiResponse(None, message="资源删除成功")

    @action(detail=True, methods=["post"], url_path="review")
    def review_question(self, request, pk=None):
        """审核试题（通过/驳回）。"""
        question = self.get_object()
        serializer = ReviewRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = serializer.validated_data["result"]
        comment = serializer.validated_data.get("comment", "")

        question.status = (
            Question.STATUS_APPROVED
            if result == QuestionReview.RESULT_APPROVED
            else Question.STATUS_REJECTED
        )
        question.reviewer = request.user
        question.save(update_fields=["status", "reviewer"])

        review = QuestionReview.objects.create(
            question=question,
            reviewer=request.user,
            result=result,
            comment=comment,
        )
        return ApiResponse(QuestionReviewSerializer(review).data, message="审核完成")

    @action(detail=True, methods=["get"], url_path="reviews")
    def list_reviews(self, request, pk=None):
        """查询试题审核记录。"""
        question = self.get_object()
        reviews = question.reviews.all()
        return ApiResponse(QuestionReviewSerializer(reviews, many=True).data)
