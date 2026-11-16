from decimal import Decimal

from rest_framework import serializers

from apps.exam.models import (
    Answer,
    AnswerSheet,
    Certificate,
    ExtracurricularUpload,
    FunContent,
    Paper,
    PaperPublish,
    PaperQuestion,
    PerformanceScore,
    UploadedCertificate,
)
from apps.classroom.models import APPROVED, ClassRoom, ClassStudent
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


class DraftQuestionSerializer(serializers.Serializer):
    """暂存试卷：单道题的逐题分值（新版 questions 格式）。"""

    question_id = serializers.IntegerField(min_value=1)
    score = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=Decimal("0"))


class DraftRequestSerializer(serializers.Serializer):
    """暂存试卷请求体：兼容新版逐题分值 questions 与旧版 question_ids。

    新版：{"questions": [{"question_id": 101, "score": 5}]}
    旧版：{"question_ids": [101, 205]}
    两者同时传入时，优先使用 questions。
    """

    questions = DraftQuestionSerializer(many=True, required=False)
    question_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False,
    )

    def validate(self, attrs):
        if not attrs.get("questions") and not attrs.get("question_ids"):
            raise serializers.ValidationError("至少需要 questions 或 question_ids")
        return attrs


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


class FunContentSerializer(serializers.ModelSerializer):
    """趣味课堂内容（含展示字段）。"""

    subject_display = serializers.CharField(source="get_subject_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    creator_name = serializers.SerializerMethodField()
    school_name = serializers.SerializerMethodField()
    target_class_name = serializers.SerializerMethodField()

    class Meta:
        model = FunContent
        fields = [
            "id",
            "title",
            "subject",
            "subject_display",
            "category",
            "summary",
            "content",
            "fun_fact",
            "emoji",
            "color",
            "read_minutes",
            "status",
            "status_display",
            "creator",
            "creator_name",
            "school",
            "school_name",
            "target_class",
            "target_class_name",
            "published_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["creator", "school", "published_at", "created_at", "updated_at"]

    def get_creator_name(self, obj):
        if not obj.creator:
            return ""
        return obj.creator.real_name or obj.creator.username

    def get_school_name(self, obj):
        return obj.school.name if obj.school else ""

    def get_target_class_name(self, obj):
        return obj.target_class.name if obj.target_class else ""


class UploadedCertificateSerializer(serializers.ModelSerializer):
    """学生上传证书（含展示字段）。"""

    cert_type_display = serializers.CharField(source="get_cert_type_display", read_only=True)
    subject_display = serializers.CharField(source="get_subject_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    student_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = UploadedCertificate
        fields = [
            "id",
            "title",
            "cert_type",
            "cert_type_display",
            "subject",
            "subject_display",
            "issuer",
            "obtained_at",
            "image",
            "image_url",
            "note",
            "status",
            "status_display",
            "student",
            "student_name",
            "class_name",
            "reviewer",
            "review_comment",
            "reviewed_at",
            "created_at",
        ]
        read_only_fields = [
            "student",
            "status",
            "reviewer",
            "review_comment",
            "reviewed_at",
            "created_at",
        ]

    def get_student_name(self, obj):
        return obj.student.real_name or obj.student.username

    def get_class_name(self, obj):
        row = (
            ClassStudent.objects.filter(student=obj.student, status=APPROVED, is_deleted=False)
            .select_related("klass")
            .first()
        )
        return row.klass.name if row and row.klass else ""

    def get_image_url(self, obj):
        if not obj.image:
            return ""
        url = obj.image.url
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url
