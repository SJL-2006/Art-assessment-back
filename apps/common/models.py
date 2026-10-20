"""公共模型：抽象基类与操作日志。"""
from django.db import models


class BaseModel(models.Model):
    """抽象基类：创建/更新时间与逻辑删除标记。"""
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    is_deleted = models.BooleanField("是否删除", default=False)
    deleted_at = models.DateTimeField("删除时间", null=True, blank=True)

    class Meta:
        abstract = True


class OperationLog(models.Model):
    """用户操作日志。"""
    user = models.ForeignKey(
        "users.User", on_delete=models.SET_NULL, null=True, blank=True, verbose_name="操作人",
        related_name="operation_logs",
    )
    action = models.CharField("操作类型", max_length=32, blank=True)
    module = models.CharField("模块", max_length=64, blank=True)
    method = models.CharField("请求方法", max_length=16)
    path = models.CharField("请求路径", max_length=255)
    ip = models.GenericIPAddressField("来源 IP", null=True, blank=True)
    detail = models.JSONField("详情", null=True, blank=True)
    created_at = models.DateTimeField("操作时间", auto_now_add=True)

    class Meta:
        db_table = "common_operation_log"
        verbose_name = "操作日志"
        verbose_name_plural = "操作日志"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.method} {self.path}"
