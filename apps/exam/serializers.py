from rest_framework import serializers

from apps.exam.models import (
    Answer,
    AnswerSheet,
    Certificate,
    ExtracurricularUpload,
    Paper,
    PaperPublish,
    PaperQuestion,
    PerformanceScore,
)


class PaperSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Paper
        fields = "__all__"

    def get_question_count(self, obj):
        return obj.paper_questions.count()


class PaperQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperQuestion
        fields = "__all__"


class PaperPublishSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperPublish
        fields = "__all__"


class AnswerSheetSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnswerSheet
        fields = "__all__"


class AnswerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Answer
        fields = "__all__"


class CertificateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Certificate
        fields = "__all__"


class PerformanceScoreSerializer(serializers.ModelSerializer):
    """平时表现评分。"""
    student_name = serializers.CharField(source="student.real_name", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True)
    scorer_name = serializers.CharField(source="scorer.real_name", read_only=True)

    class Meta:
        model = PerformanceScore
        fields = "__all__"


class ExtracurricularUploadSerializer(serializers.ModelSerializer):
    """学生课外学习成果。"""

    class Meta:
        model = ExtracurricularUpload
        fields = "__all__"
        read_only_fields = ["student"]
