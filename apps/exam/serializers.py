from rest_framework import serializers

from apps.exam.models import Answer, AnswerSheet, Certificate, Paper, PaperPublish, PaperQuestion


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
