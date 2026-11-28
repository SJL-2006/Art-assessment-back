from rest_framework import serializers

from apps.questionbank.models import Chapter, Course, Question, QuestionResource, QuestionReview


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = "__all__"


class ChapterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chapter
        fields = "__all__"


class QuestionResourceSerializer(serializers.ModelSerializer):
    """试题资源：file 必填、rtype 由模型 choices 校验。

    嵌套路由（questions/{pk}/resources/）创建时由 save(question=question) 注入；
    独立路由（resources/）创建时从请求体读取 question。
    """

    class Meta:
        model = QuestionResource
        fields = "__all__"


class QuestionSerializer(serializers.ModelSerializer):
    resources = QuestionResourceSerializer(many=True, read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    chapter_name = serializers.CharField(source="chapter.name", read_only=True)
    creator_name = serializers.SerializerMethodField()
    creator_role = serializers.SerializerMethodField()
    score = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True,
        help_text="可选。组卷时由教师为每道题赋分，此字段可留空。",
    )

    class Meta:
        model = Question
        fields = "__all__"

    def get_creator_name(self, obj) -> str:
        """创建人展示名：优先真实姓名，其次用户名。"""
        if not obj.creator:
            return ""
        return obj.creator.real_name or obj.creator.username

    def get_creator_role(self, obj) -> str:
        """创建人分类：管理员 / 教师（「创建人」筛选使用）。"""
        role = getattr(obj.creator, "role", "") if obj.creator else ""
        if role in ("qb_admin", "province"):
            return "管理员"
        if role == "teacher":
            return "教师"
        return ""


class QuestionReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionReview
        fields = "__all__"


class ReviewRequestSerializer(serializers.Serializer):
    """审核请求体，仅接收 result 与 comment。"""

    result = serializers.ChoiceField(choices=QuestionReview.RESULT_CHOICES)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
