"""测评核心：试卷、发布、答卷、成绩、证书。"""
from django.db import models

from apps.common.models import BaseModel


class Paper(BaseModel):
    """试卷。"""
    TYPE_PRACTICE = "practice"
    TYPE_FORMAL = "formal"
    TYPE_CHOICES = [
        (TYPE_PRACTICE, "练习"),
        (TYPE_FORMAL, "正式测评"),
    ]
    SUBJECT_MUSIC = "music"
    SUBJECT_ART = "art"
    SUBJECT_CHOICES = [
        (SUBJECT_MUSIC, "音乐"),
        (SUBJECT_ART, "美术"),
    ]
    LEVEL_CLASS = "class"
    LEVEL_SCHOOL = "school"
    LEVEL_DISTRICT = "district"
    LEVEL_CITY = "city"
    LEVEL_PROVINCE = "province"
    LEVEL_CHOICES = [
        (LEVEL_CLASS, "班级"),
        (LEVEL_SCHOOL, "学校"),
        (LEVEL_DISTRICT, "区县"),
        (LEVEL_CITY, "市州"),
        (LEVEL_PROVINCE, "省级"),
    ]
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CLOSED = "closed"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "草稿"),
        (STATUS_PUBLISHED, "已发布"),
        (STATUS_CLOSED, "已结束"),
    ]

    title = models.CharField("试卷标题", max_length=128)
    ptype = models.CharField("类型", max_length=16, choices=TYPE_CHOICES, default=TYPE_PRACTICE)
    subject = models.CharField("学科", max_length=16, choices=SUBJECT_CHOICES)
    level = models.CharField("适用范围", max_length=16, choices=LEVEL_CHOICES, default=LEVEL_CLASS)
    grade = models.CharField("年级", max_length=32, blank=True)
    duration = models.IntegerField("限时(分钟)", default=0)
    total_score = models.DecimalField("总分", max_digits=6, decimal_places=2, default=0)
    status = models.CharField("状态", max_length=16, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    creator = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="created_papers", verbose_name="创建人",
    )

    class Meta:
        db_table = "exam_paper"
        verbose_name = "试卷"
        verbose_name_plural = "试卷"

    def __str__(self):
        return self.title


class PaperQuestion(BaseModel):
    """试卷-试题关联（含题号与分值）。"""
    paper = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="paper_questions", verbose_name="试卷",
    )
    question = models.ForeignKey(
        "questionbank.Question", on_delete=models.CASCADE,
        related_name="paper_questions", verbose_name="试题",
    )
    sort = models.IntegerField("题号", default=0)
    score = models.DecimalField("分值", max_digits=5, decimal_places=2, default=1)

    class Meta:
        db_table = "exam_paper_question"
        verbose_name = "试卷试题"
        verbose_name_plural = "试卷试题"
        ordering = ["sort"]
        unique_together = [("paper", "question")]


class PaperPublish(BaseModel):
    """试卷发布记录。"""
    SCOPE_CLASS = "class"
    SCOPE_SCHOOL = "school"
    SCOPE_GRADE = "grade"
    SCOPE_REGION = "region"
    SCOPE_CHOICES = [
        (SCOPE_CLASS, "班级"),
        (SCOPE_SCHOOL, "学校"),
        (SCOPE_GRADE, "年级"),
        (SCOPE_REGION, "行政区"),
    ]
    STATUS_PUBLISHED = "published"
    STATUS_RECALLED = "recalled"
    STATUS_CHOICES = [
        (STATUS_PUBLISHED, "已发布"),
        (STATUS_RECALLED, "已撤回"),
    ]

    paper = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="publishes", verbose_name="试卷",
    )
    scope_type = models.CharField("发布范围类型", max_length=16, choices=SCOPE_CHOICES)
    target_school = models.ForeignKey(
        "org.School", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="目标学校",
    )
    target_class = models.ForeignKey(
        "classroom.ClassRoom", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="目标班级",
    )
    target_region = models.ForeignKey(
        "org.Region", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="目标行政区",
    )
    start_at = models.DateTimeField("开始时间", null=True, blank=True)
    end_at = models.DateTimeField("结束时间", null=True, blank=True)
    status = models.CharField("状态", max_length=16, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)

    class Meta:
        db_table = "exam_paper_publish"
        verbose_name = "试卷发布"
        verbose_name_plural = "试卷发布"


class AnswerSheet(BaseModel):
    """答卷。"""
    paper = models.ForeignKey(
        Paper, on_delete=models.CASCADE, related_name="answer_sheets", verbose_name="试卷",
    )
    student = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="answer_sheets", verbose_name="学生",
    )
    publish = models.ForeignKey(
        PaperPublish, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="发布记录",
    )
    started_at = models.DateTimeField("开始作答时间", null=True, blank=True)
    submitted_at = models.DateTimeField("提交时间", null=True, blank=True)
    is_submitted = models.BooleanField("是否已提交", default=False)
    total_score = models.DecimalField("得分", max_digits=6, decimal_places=2, default=0)

    class Meta:
        db_table = "exam_answer_sheet"
        verbose_name = "答卷"
        verbose_name_plural = "答卷"
        unique_together = [("paper", "student", "publish")]


class Answer(BaseModel):
    """答题明细。"""
    sheet = models.ForeignKey(
        AnswerSheet, on_delete=models.CASCADE, related_name="answers", verbose_name="答卷",
    )
    question = models.ForeignKey(
        "questionbank.Question", on_delete=models.CASCADE,
        related_name="answer_records", verbose_name="试题",
    )
    answer = models.TextField("作答内容", blank=True)
    is_correct = models.BooleanField("是否正确", null=True, blank=True)
    score = models.DecimalField("得分", max_digits=5, decimal_places=2, default=0)

    class Meta:
        db_table = "exam_answer"
        verbose_name = "答题明细"
        verbose_name_plural = "答题明细"


class PerformanceScore(BaseModel):
    """平时表现评分（教师对学生日常艺术表现的评分）。"""
    student = models.ForeignKey(
        "users.User", on_delete=models.CASCADE,
        related_name="performance_scores", verbose_name="学生",
    )
    klass = models.ForeignKey(
        "classroom.ClassRoom", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="performance_scores", verbose_name="班级",
    )
    course = models.ForeignKey(
        "questionbank.Course", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="performance_scores", verbose_name="学科",
    )
    scorer = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="given_performance_scores", verbose_name="评分教师",
    )
    score = models.DecimalField("评分", max_digits=5, decimal_places=2, default=0)
    comment = models.TextField("评语", blank=True)

    class Meta:
        db_table = "exam_performance_score"
        verbose_name = "平时表现评分"
        verbose_name_plural = "平时表现评分"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student} - {self.score}"


class ExtracurricularUpload(BaseModel):
    """学生课外自主学习成果（图片）。"""
    student = models.ForeignKey(
        "users.User", on_delete=models.CASCADE,
        related_name="extracurricular_uploads", verbose_name="学生",
    )
    title = models.CharField("标题", max_length=128)
    image = models.FileField("图片", upload_to="extracurricular/%Y/%m/")
    description = models.TextField("说明", blank=True)

    class Meta:
        db_table = "exam_extracurricular_upload"
        verbose_name = "课外学习上传"
        verbose_name_plural = "课外学习上传"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Certificate(BaseModel):
    """证书。"""
    student = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="certificates", verbose_name="学生",
    )
    sheet = models.ForeignKey(
        AnswerSheet, on_delete=models.CASCADE, null=True, blank=True,
        related_name="certificates", verbose_name="关联答卷",
    )
    subject = models.CharField("学科", max_length=16, choices=Paper.SUBJECT_CHOICES)
    title = models.CharField("证书名称", max_length=128)
    file = models.FileField("证书文件", upload_to="certificates/", blank=True)

    class Meta:
        db_table = "exam_certificate"
        verbose_name = "证书"
        verbose_name_plural = "证书"

    def __str__(self):
        return self.title
