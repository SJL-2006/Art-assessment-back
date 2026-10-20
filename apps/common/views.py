"""通用 ViewSet 基类。"""
from rest_framework import viewsets

from apps.common.response import ApiResponse


class BaseViewSet(viewsets.ModelViewSet):
    """项目统一 ViewSet 基类：删除返回 200 + 信封（替代 DRF 默认 204）。"""

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return ApiResponse(None, message="删除成功")
