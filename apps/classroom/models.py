"""班级与师生关系。"""
from django.db import models

from apps.common.models import BaseModel

PENDING = "pending"
APPROVED = "approved"
REJECTED = "rejected"
STATUS_CHOICES = [
    (PENDING, "待审核"),
    (APPROVED, "已通过"),
    (REJECTED, "已拒绝"),
]


class ClassRoom(BaseModel):
    """班级。"""
    name = models.CharField("班级名称", max_length=128)
    code = models.CharField("班级编号", max_length=64, unique=True)
    grade = models.CharField("年级", max_length=32, blank=True)
    school = models.ForeignKey(
        "org.School", on_delete=models.CASCADE, related_name="classes", verbose_name="所属学校",
    )
    head_teacher = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="managed_classes", verbose_name="班主任",
    )

    class Meta:
        db_table = "classroom_class"
        verbose_name = "班级"
        verbose_name_plural = "班级"

    def __str__(self):
        return self.name


class ClassStudent(BaseModel):
    """学生加入班级（含审核状态）。"""
    klass = models.ForeignKey(
        ClassRoom, on_delete=models.CASCADE, related_name="students", verbose_name="班级",
    )
    student = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="class_memberships", verbose_name="学生",
    )
    status = models.CharField("状态", max_length=16, choices=STATUS_CHOICES, default=PENDING)

    class Meta:
        db_table = "classroom_class_student"
        verbose_name = "班级学生"
        unique_together = [("klass", "student")]


class ClassTeacher(BaseModel):
    """教师任教班级（含审核状态）。"""
    klass = models.ForeignKey(
        ClassRoom, on_delete=models.CASCADE, related_name="teachers", verbose_name="班级",
    )
    teacher = models.ForeignKey(
        "users.User", on_delete=models.CASCADE, related_name="class_teachings", verbose_name="教师",
    )
    course = models.ForeignKey(
        "questionbank.Course", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="任教学科",
    )
    status = models.CharField("状态", max_length=16, choices=STATUS_CHOICES, default=PENDING)

    class Meta:
        db_table = "classroom_class_teacher"
        verbose_name = "班级教师"
        unique_together = [("klass", "teacher", "course")]
