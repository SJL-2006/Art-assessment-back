from decimal import Decimal

from rest_framework import serializers

from apps.classroom.models import ClassRoom
from apps.exam.models import Answer, AnswerSheet, Certificate, Paper, PaperPublish, PaperQuestion
from apps.org.models import Region, School
from apps.questionbank.models import Question
from apps.questionbank.serializers import QuestionSerializer


class PaperSerializer(serializers.ModelSerializer):
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Paper
        fields = "__all__"

    def get_question_count(self, obj) -> int:
        return obj.paper_questions.count()


class PaperQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaperQuestion
        fields = "__all__"


class PaperQuestionDetailSerializer(serializers.ModelSerializer):
    """试卷试题（含完整题目内容）。"""

    question = QuestionSerializer(read_only=True)

    class Meta:
        model = PaperQuestion
        fields = "__all__"


class PaperDetailSerializer(serializers.ModelSerializer):
    """试卷详情（含完整题目）。"""

    paper_questions = PaperQuestionDetailSerializer(many=True, read_only=True)
    question_count = serializers.SerializerMethodField()

    class Meta:
        model = Paper
        fields = "__all__"

    def get_question_count(self, obj) -> int:
        return obj.paper_questions.count()


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


class QtypeConfigSerializer(serializers.Serializer):
    """自动组卷：单种题型的抽题配置。"""

    qtype = serializers.ChoiceField(choices=Question.TYPE_CHOICES)
    count = serializers.IntegerField(min_value=1)
    difficulty = serializers.ChoiceField(choices=Question.DIFFICULTY_CHOICES)


class AutoGenerateRequestSerializer(serializers.Serializer):
    """自动组卷请求体。"""

    subject = serializers.ChoiceField(choices=Paper.SUBJECT_CHOICES)
    grade = serializers.CharField(required=False, allow_blank=True, max_length=32)
    chapter_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, allow_empty=True,
    )
    qtype_config = QtypeConfigSerializer(many=True)
    total_score = serializers.DecimalField(
        required=False, max_digits=6, decimal_places=2, min_value=Decimal("0"),
    )
    title = serializers.CharField(max_length=128)
    ptype = serializers.ChoiceField(choices=Paper.TYPE_CHOICES, required=False)
    level = serializers.ChoiceField(choices=Paper.LEVEL_CHOICES, required=False)

    def validate_qtype_config(self, value):
        if not value:
            raise serializers.ValidationError("qtype_config 不能为空")
        return value


class DraftRequestSerializer(serializers.Serializer):
    """暂存试卷请求体：按顺序重建试题关联。"""

    question_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=False,
    )


class PublishCreateSerializer(serializers.Serializer):
    """发布试卷请求体：含 scope 交叉校验。"""

    paper = serializers.PrimaryKeyRelatedField(queryset=Paper.objects.all())
    scope_type = serializers.ChoiceField(choices=PaperPublish.SCOPE_CHOICES)
    target_school = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.all(), required=False, allow_null=True,
    )
    target_class = serializers.PrimaryKeyRelatedField(
        queryset=ClassRoom.objects.all(), required=False, allow_null=True,
    )
    target_region = serializers.PrimaryKeyRelatedField(
        queryset=Region.objects.all(), required=False, allow_null=True,
    )
    grade = serializers.CharField(required=False, allow_blank=True, max_length=32)
    start_at = serializers.DateTimeField(required=False, allow_null=True)
    end_at = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, attrs):
        paper = attrs["paper"]
        if paper.status not in (Paper.STATUS_DRAFT, Paper.STATUS_PUBLISHED):
            raise serializers.ValidationError({"paper": "试卷状态必须为草稿或已发布才能发布"})

        scope_type = attrs["scope_type"]
        if scope_type == PaperPublish.SCOPE_CLASS:
            if not attrs.get("target_school"):
                raise serializers.ValidationError({"target_school": "scope_type=class 时 target_school 必填"})
            if not attrs.get("target_class"):
                raise serializers.ValidationError({"target_class": "scope_type=class 时 target_class 必填"})
        elif scope_type == PaperPublish.SCOPE_SCHOOL:
            if not attrs.get("target_school"):
                raise serializers.ValidationError({"target_school": "scope_type=school 时 target_school 必填"})
        elif scope_type == PaperPublish.SCOPE_REGION:
            if not attrs.get("target_region"):
                raise serializers.ValidationError({"target_region": "scope_type=region 时 target_region 必填"})
        # scope_type=grade：无必填 target，grade 可选
        return attrs
