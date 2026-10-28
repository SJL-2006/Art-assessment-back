"""组织架构：行政区划与学校。"""
from django.db import models

from apps.common.models import BaseModel


class Region(BaseModel):
    """行政区划（省 / 市州 / 区县 三级）。"""
    LEVEL_PROVINCE = "province"
    LEVEL_CITY = "city"
    LEVEL_DISTRICT = "district"
    LEVEL_CHOICES = [
        (LEVEL_PROVINCE, "省"),
        (LEVEL_CITY, "市州"),
        (LEVEL_DISTRICT, "区县"),
    ]

    name = models.CharField("名称", max_length=64)
    code = models.CharField("行政区代码", max_length=32, unique=True)
    level = models.CharField("层级", max_length=16, choices=LEVEL_CHOICES)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, null=True, blank=True,
        related_name="children", verbose_name="上级",
    )

    class Meta:
        db_table = "org_region"
        verbose_name = "行政区"
        verbose_name_plural = "行政区"

    def __str__(self):
        return self.name


class School(BaseModel):
    """学校。"""
    name = models.CharField("学校名称", max_length=128)
    code = models.CharField("学校代码", max_length=64, unique=True)
    region = models.ForeignKey(
        Region, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="schools", verbose_name="所属区县",
    )
    address = models.CharField("地址", max_length=255, blank=True)
    contact = models.CharField("联系人", max_length=64, blank=True)
    phone = models.CharField("联系电话", max_length=32, blank=True)
    is_directly_affiliated = models.BooleanField("市直属", default=False)

    class Meta:
        db_table = "org_school"
        verbose_name = "学校"
        verbose_name_plural = "学校"

    def __str__(self):
        return self.name
