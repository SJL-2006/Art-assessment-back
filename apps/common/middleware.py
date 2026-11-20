"""操作日志中间件：记录非只读请求。"""
from django.conf import settings


class OperationLogMiddleware:
    MODULE_LABELS = {
        "exam": "测评",
        "questionbank": "题库",
        "users": "用户",
        "auth": "登录认证",
        "org": "组织",
        "classroom": "班级",
        "common": "系统",
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._log(request)
        return response

    @classmethod
    def _module(cls, path):
        """从 /api/<模块>/... 中提取模块标识，供日志列表展示。"""
        parts = [part for part in path.strip("/").split("/") if part]
        if len(parts) > 1 and parts[0] == "api":
            return cls.MODULE_LABELS.get(parts[1], parts[1])
        return parts[0] if parts else ""

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
                module=self._module(request.path),
                method=request.method,
                path=request.path,
                ip=request.META.get("REMOTE_ADDR"),
            )
        except Exception:  # 日志失败不影响主流程
            pass
