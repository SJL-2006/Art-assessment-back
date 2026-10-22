"""全局异常处理与自定义业务异常。"""
import logging

from django.http import Http404
from rest_framework import exceptions as drf_exc
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.common.response import ErrorCode

logger = logging.getLogger("django")


class ApiException(Exception):
    """业务异常：message 给客户端，code/status 控制响应。"""

    def __init__(self, message, code=ErrorCode.INVALID_PARAM, status=400):
        self.message = message
        self.code = code
        self.status = status
        super().__init__(message)


def custom_exception_handler(exc, context):
    # Django Http404（get_object_or_404 抛出，不是 DRF 的 NotFound）
    if isinstance(exc, Http404):
        return Response(
            {"code": ErrorCode.NOT_FOUND, "message": "资源不存在", "data": None},
            status=404,
        )

    response = exception_handler(exc, context)

    # DRF 能识别的异常
    if response is not None:
        if isinstance(exc, drf_exc.ValidationError):
            return Response(
                {"code": ErrorCode.INVALID_PARAM, "message": "参数校验失败", "data": exc.detail},
                status=response.status_code,
            )
        if isinstance(exc, drf_exc.AuthenticationFailed):
            return Response(
                {"code": ErrorCode.UNAUTHORIZED, "message": "认证失败或凭证已过期", "data": None},
                status=401,
            )
        if isinstance(exc, drf_exc.NotAuthenticated):
            return Response(
                {"code": ErrorCode.UNAUTHORIZED, "message": "未登录", "data": None},
                status=401,
            )
        if isinstance(exc, drf_exc.PermissionDenied):
            return Response(
                {"code": ErrorCode.FORBIDDEN, "message": "没有操作权限", "data": None},
                status=403,
            )
        if isinstance(exc, drf_exc.NotFound):
            return Response(
                {"code": ErrorCode.NOT_FOUND, "message": "资源不存在", "data": None},
                status=404,
            )
        # 兜底：DRF 返回了 response 但我们没显式处理的类型
        detail = getattr(exc, "detail", None) or str(exc)
        return Response(
            {"code": response.status_code, "message": str(detail), "data": None},
            status=response.status_code,
        )

    # 自定义业务异常
    if isinstance(exc, ApiException):
        return Response(
            {"code": exc.code, "message": exc.message, "data": None},
            status=exc.status,
        )

    # 未捕获异常：仅记录日志，不向客户端泄露细节
    logger.exception("未处理的异常: %s", exc)
    return Response(
        {"code": ErrorCode.SERVER_ERROR, "message": "服务器内部错误", "data": None},
        status=500,
    )
