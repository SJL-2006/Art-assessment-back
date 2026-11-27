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

    @staticmethod
    def _resolve_user(request):
        """解析操作人。

        JWT 由 DRF 层校验，Django 中间件里 request.user 恒为 AnonymousUser；
        因此优先从 Authorization 头解出 user_id，session 认证（如 admin）兜底。
        """
        if request.user.is_authenticated:
            return request.user
        auth = request.META.get("HTTP_AUTHORIZATION", "")
        if not auth.startswith("Bearer "):
            return None
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.exceptions import TokenError
        from rest_framework_simplejwt.tokens import AccessToken

        try:
            user_id = AccessToken(auth.split(" ", 1)[1]).get("user_id")
        except (TokenError, Exception):
            return None
        if user_id is None:
            return None
        user_model = get_user_model()
        return user_model.objects.filter(pk=user_id, is_active=True).first()

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
                user=self._resolve_user(request),
                action=request.method,
                module=self._module(request.path),
                method=request.method,
                path=request.path,
                ip=request.META.get("REMOTE_ADDR"),
            )
        except Exception:  # 日志失败不影响主流程
            pass
