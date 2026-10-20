"""自定义用户模型与角色。"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """统一用户：不同角色共用一张表，通过 role 区分。"""

    ROLE_STUDENT = "student"
    ROLE_TEACHER = "teacher"
    ROLE_SCHOOL = "school"
    ROLE_DISTRICT = "district"
    ROLE_CITY = "city"
    ROLE_PROVINCE = "province"
    ROLE_QB_ADMIN = "qb_admin"

    ROLE_CHOICES = [
        (ROLE_STUDENT, "学生"),
        (ROLE_TEACHER, "教师"),
        (ROLE_SCHOOL, "学校管理员"),
        (ROLE_DISTRICT, "区县管理员"),
        (ROLE_CITY, "市州管理员"),
        (ROLE_PROVINCE, "省级管理员"),
        (ROLE_QB_ADMIN, "题库管理员"),
    ]

    role = models.CharField("角色", max_length=16, choices=ROLE_CHOICES, default=ROLE_STUDENT)
    real_name = models.CharField("真实姓名", max_length=32, blank=True)
    phone = models.CharField("手机号", max_length=20, blank=True)
    avatar = models.FileField("头像", upload_to="avatars/", blank=True)
    student_no = models.CharField("学籍号", max_length=64, blank=True)
    bio = models.TextField("简介", blank=True)

    school = models.ForeignKey(
        "org.School", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="users", verbose_name="所属学校",
    )
    region = models.ForeignKey(
        "org.Region", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="users", verbose_name="所属行政区",
    )

    class Meta:
        db_table = "users_user"
        verbose_name = "用户"
        verbose_name_plural = "用户"

    def __str__(self):
        return f"{self.username}({self.get_role_display()})"
