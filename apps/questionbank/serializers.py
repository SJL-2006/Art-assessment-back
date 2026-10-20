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
    class Meta:
        model = QuestionResource
        fields = "__all__"


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
