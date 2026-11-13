"""题库：课程、章节、试题及其嵌套资源与审核接口。"""
from django.db.models import Case, IntegerField, Value, When
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.views import APIView

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

# 各管理端在手动组卷时需要浏览题库，故对课程/章节/试题开放只读权限
MANAGEMENT_ROLES = (
    User.ROLE_SCHOOL,
    User.ROLE_DISTRICT,
    User.ROLE_CITY,
    User.ROLE_PROVINCE,
)
CATALOG_READ_ROLES = (User.ROLE_STUDENT, User.ROLE_TEACHER, User.ROLE_QB_ADMIN) + MANAGEMENT_ROLES
QUESTION_READ_ROLES = (User.ROLE_TEACHER, User.ROLE_QB_ADMIN) + MANAGEMENT_ROLES


class CourseViewSet(BaseViewSet):
    """课程 CRUD。"""
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["id"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [has_role(*CATALOG_READ_ROLES)()]
        return [has_role(User.ROLE_QB_ADMIN)()]


class ChapterViewSet(BaseViewSet):
    """章节 CRUD。"""
    queryset = Chapter.objects.all()
    serializer_class = ChapterSerializer
    search_fields = ["name"]
    ordering_fields = ["id", "sort"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [has_role(*CATALOG_READ_ROLES)()]
        return [has_role(User.ROLE_QB_ADMIN)()]

    def get_queryset(self):
        qs = super().get_queryset()
        course = self.request.query_params.get("course")
        if course:
            qs = qs.filter(course_id=course)
        return qs


# 年级排序键：小学 → 初中 → 高中（一年级…高三），空值/未知排最后
_GRADES = [
    "一年级", "二年级", "三年级", "四年级", "五年级", "六年级",
    "七年级", "八年级", "九年级", "高一", "高二", "高三",
]
GRADE_ORDER = Case(
    *[When(grade=g, then=Value(i)) for i, g in enumerate(_GRADES, start=1)],
    default=Value(len(_GRADES) + 1),
    output_field=IntegerField(),
)


class QuestionViewSet(BaseViewSet):
    """试题 CRUD 及嵌套资源/审核接口。"""
    # 默认排序：按学科（音乐在前、美术在后）→ 年级（一年级…高三）→ id，
    # 使音乐/美术各自连在一起、组内按年级有序，便于题库浏览。
    queryset = (
        Question.objects.select_related("course", "chapter")
        .annotate(
            subject_order=Case(
                When(course__code="art", then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("subject_order", GRADE_ORDER, "id")
    )
    serializer_class = QuestionSerializer
    search_fields = ["stem"]
    ordering_fields = ["id", "difficulty", "score"]

    def get_permissions(self):
        if self.action in ("review_question", "list_reviews"):
            return [has_role(User.ROLE_QB_ADMIN)()]
        if self.action in ("list", "retrieve"):
            return [has_role(*QUESTION_READ_ROLES)()]
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
        # 学科筛选（音乐/美术）：按课程代码过滤。音乐可能拆分为多个课程
        # （如 音乐鉴赏 / 初中音乐 / 高中音乐 / 小学音乐，code 均为 "music"），
        # 因此不能只按单个 course_id 过滤，需按 course.code 聚合。
        subject = params.get("subject")
        if subject:
            code = "art" if subject in ("art", "美术") else "music"
            qs = qs.filter(course__code=code)
        return qs

    @extend_schema(
        request=QuestionResourceSerializer,
        responses={201: QuestionResourceSerializer},
    )
    @action(detail=True, methods=["post"], url_path="resources")
    def upload_resource(self, request, pk=None):
        """上传试题资源（音频/图片/视频）。"""
        question = self.get_object()
        serializer = QuestionResourceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(question=question)
        return ApiResponse(serializer.data, message="资源上传成功", status=201)

    @extend_schema(responses={200: None})
    def delete_resource(self, request, pk=None, rid=None):
        """删除指定试题资源。"""
        question = self.get_object()
        try:
            resource = question.resources.get(pk=rid)
        except QuestionResource.DoesNotExist:
            raise ApiException("资源不存在", code=ErrorCode.NOT_FOUND, status=404)
        resource.delete()
        return ApiResponse(None, message="资源删除成功")

    @extend_schema(
        request=ReviewRequestSerializer,
        responses={200: QuestionReviewSerializer},
    )
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

    @extend_schema(
        responses={200: QuestionReviewSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="reviews")
    def list_reviews(self, request, pk=None):
        """查询试题审核记录。"""
        question = self.get_object()
        reviews = question.reviews.all()
        return ApiResponse(QuestionReviewSerializer(reviews, many=True).data)


# 试题资源独立管理：列表/详情对教师、题库管理员、省级开放；写操作仅题库管理员、省级
RESOURCE_READ_ROLES = (User.ROLE_TEACHER, User.ROLE_QB_ADMIN, User.ROLE_PROVINCE)
RESOURCE_WRITE_ROLES = (User.ROLE_QB_ADMIN, User.ROLE_PROVINCE)


class QuestionResourceViewSet(BaseViewSet):
    """试题资源独立管理（音频/图片/视频）。"""

    queryset = QuestionResource.objects.all()
    serializer_class = QuestionResourceSerializer
    search_fields = []
    ordering_fields = ["id"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [has_role(*RESOURCE_READ_ROLES)()]
        return [has_role(*RESOURCE_WRITE_ROLES)()]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        question = params.get("question")
        rtype = params.get("rtype")
        if question:
            qs = qs.filter(question_id=question)
        if rtype:
            qs = qs.filter(rtype=rtype)
        return qs


class QuestionTypeOptionsView(APIView):
    """GET /api/questionbank/question-types/ 题型字典（组卷/题库下拉使用，含填空题）。"""

    permission_classes = [has_role(*QUESTION_READ_ROLES)]

    def get(self, request):
        return ApiResponse(
            data=[{"value": code, "label": label} for code, label in Question.TYPE_CHOICES]
        )
