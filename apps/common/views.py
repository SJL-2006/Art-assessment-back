"""通用 ViewSet 基类。"""
from django.utils import timezone
from rest_framework import viewsets

from apps.common.response import ApiResponse


class BaseViewSet(viewsets.ModelViewSet):
    """项目统一 ViewSet 基类。

    - get_queryset 默认过滤软删除数据
    - destroy 改为软删除（is_deleted=True + deleted_at=now）
    - 删除接口返回 200 + 信封（替代 DRF 默认 204）
    """

    def get_queryset(self):
        qs = super().get_queryset()
        # 自动过滤软删除
        if hasattr(qs.model, "is_deleted"):
            qs = qs.filter(is_deleted=False)
        return qs

    def perform_destroy(self, instance):
        """软删除：标记 is_deleted + deleted_at。"""
        if hasattr(instance, "is_deleted"):
            instance.is_deleted = True
            instance.deleted_at = timezone.now()
            instance.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        else:
            instance.delete()

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return ApiResponse(None, message="删除成功")
