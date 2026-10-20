"""操作日志中间件：记录非只读请求。"""
from django.conf import settings


class OperationLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._log(request)
        return response

    def _log(self, request):
        if not getattr(settings, "OPERATION_LOG_ENABLED", False):
            return
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return
        if request.path.startswith(("/admin/", "/static/", "/media/")):
            return
        try:
            from apps.common.models import OperationLog

            OperationLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action=request.method,
                method=request.method,
                path=request.path,
                ip=request.META.get("REMOTE_ADDR"),
            )
        except Exception:  # 日志失败不影响主流程
            pass
