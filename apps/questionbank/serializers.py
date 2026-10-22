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
    """试题资源：file 必填、rtype 由模型 choices 校验；question 由嵌套路由注入，设为只读。"""

    class Meta:
        model = QuestionResource
        fields = "__all__"
        read_only_fields = ["question"]


class QuestionSerializer(serializers.ModelSerializer):
    resources = QuestionResourceSerializer(many=True, read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    chapter_name = serializers.CharField(source="chapter.name", read_only=True)

    class Meta:
        model = Question
        fields = "__all__"


class QuestionReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionReview
        fields = "__all__"


class ReviewRequestSerializer(serializers.Serializer):
    """审核请求体，仅接收 result 与 comment。"""

    result = serializers.ChoiceField(choices=QuestionReview.RESULT_CHOICES)
    comment = serializers.CharField(required=False, allow_blank=True, default="")
