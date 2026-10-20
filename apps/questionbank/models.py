"""题库：课程、章节、试题、试题资源、试题审核。"""
from django.db import models

from apps.common.models import BaseModel


class Course(BaseModel):
    """课程（音乐 / 美术）。"""
    name = models.CharField("课程名称", max_length=64, unique=True)
    code = models.CharField("课程代码", max_length=32, blank=True)
    description = models.TextField("描述", blank=True)

    class Meta:
        db_table = "qb_course"
        verbose_name = "课程"
        verbose_name_plural = "课程"

    def __str__(self):
        return self.name


class Chapter(BaseModel):
    """章节（可多级）。"""
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="chapters", verbose_name="所属课程",
    )
    name = models.CharField("章节名称", max_length=128)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True,
        related_name="children", verbose_name="上级章节",
    )
    sort = models.IntegerField("排序", default=0)

    class Meta:
        db_table = "qb_chapter"
        verbose_name = "章节"
        verbose_name_plural = "章节"

    def __str__(self):
        return self.name


class Question(BaseModel):
    """试题。"""
    TYPE_CHOICES = [
        ("single", "单选题"),
        ("multiple", "多选题"),
        ("judge", "判断题"),
        ("fill", "填空题"),
        ("short", "简答题"),
        ("listening", "听力题"),
        ("sight", "视唱/识谱题"),
    ]
    DIFFICULTY_CHOICES = [
        ("easy", "简单"),
        ("medium", "中等"),
        ("hard", "困难"),
    ]
    STATUS_DRAFT = "draft"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "草稿"),
        (STATUS_PENDING, "待审核"),
        (STATUS_APPROVED, "已通过"),
        (STATUS_REJECTED, "已驳回"),
    ]

    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="questions", verbose_name="学科",
    )
    chapter = models.ForeignKey(
        Chapter, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="questions", verbose_name="章节",
    )
    qtype = models.CharField("题型", max_length=16, choices=TYPE_CHOICES)
    difficulty = models.CharField("难度", max_length=16, choices=DIFFICULTY_CHOICES, default="medium")
    grade = models.CharField("适用年级", max_length=32, blank=True)
    stem = models.TextField("题干")
    options = models.JSONField("选项", default=list, blank=True)  # [{"key": "A", "text": "..."}]
    answer = models.TextField("参考答案", blank=True)
    analysis = models.TextField("解析", blank=True)
    score = models.DecimalField("分值", max_digits=5, decimal_places=2, default=1)
    status = models.CharField("状态", max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    creator = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_questions", verbose_name="创建人",
    )
    reviewer = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="reviewed_questions", verbose_name="审核人",
    )

    class Meta:
        db_table = "qb_question"
        verbose_name = "试题"
        verbose_name_plural = "试题"
        ordering = ["-id"]

    def __str__(self):
        return self.stem[:30]


class QuestionResource(BaseModel):
    """试题资源（音频/图片/视频）。"""
    RESOURCE_AUDIO = "audio"
    RESOURCE_IMAGE = "image"
    RESOURCE_VIDEO = "video"
    TYPE_CHOICES = [
        (RESOURCE_AUDIO, "音频"),
        (RESOURCE_IMAGE, "图片"),
        (RESOURCE_VIDEO, "视频"),
    ]

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="resources", verbose_name="所属试题",
    )
    rtype = models.CharField("资源类型", max_length=16, choices=TYPE_CHOICES)
    file = models.FileField("文件", upload_to="question/%Y/%m/")

    class Meta:
        db_table = "qb_question_resource"
        verbose_name = "试题资源"
        verbose_name_plural = "试题资源"


class QuestionReview(BaseModel):
    """试题审核记录。"""
    RESULT_APPROVED = "approved"
    RESULT_REJECTED = "rejected"
    RESULT_CHOICES = [
        (RESULT_APPROVED, "通过"),
        (RESULT_REJECTED, "驳回"),
    ]

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="reviews", verbose_name="试题",
    )
    reviewer = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="审核人",
    )
    result = models.CharField("审核结果", max_length=16, choices=RESULT_CHOICES)
    comment = models.TextField("审核意见", blank=True)

    class Meta:
        db_table = "qb_question_review"
        verbose_name = "试题审核"
        verbose_name_plural = "试题审核"
