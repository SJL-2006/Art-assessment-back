"""内容模块：学生素质教育展示（趣味课堂知识）。"""
from django.db import models

from apps.common.models import BaseModel


class FunClassKnowledge(BaseModel):
    """趣味课堂知识（学生端素质教育展示）。"""

    SUBJECT_MUSIC = "music"
    SUBJECT_ART = "art"
    SUBJECT_CHOICES = [
        (SUBJECT_MUSIC, "音乐"),
        (SUBJECT_ART, "美术"),
    ]

    title = models.CharField("标题", max_length=200)
    subject = models.CharField("学科", max_length=16, choices=SUBJECT_CHOICES, blank=True)
    content = models.TextField("内容", blank=True)
    image = models.FileField("图片", upload_to="fun_class/", blank=True)
    sort = models.IntegerField("排序", default=0)
    is_published = models.BooleanField("是否发布", default=True)

    class Meta:
        db_table = "content_fun_class_knowledge"
        verbose_name = "趣味课堂知识"
        verbose_name_plural = "趣味课堂知识"
        ordering = ["sort", "-created_at"]

    def __str__(self):
        return self.title
