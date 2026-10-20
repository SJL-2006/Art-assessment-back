"""统一响应结构与错误码。"""
from rest_framework.response import Response


class ErrorCode:
    """业务错误码约定。"""
    SUCCESS = 0
    INVALID_PARAM = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    SERVER_ERROR = 500


class ApiResponse(Response):
    """统一响应：{"code": 0, "message": "ok", "data": ...}"""

    def __init__(self, data=None, code=ErrorCode.SUCCESS, message="ok", status=200, **kwargs):
        payload = {"code": code, "message": message, "data": data}
        super().__init__(payload, status=status, **kwargs)
