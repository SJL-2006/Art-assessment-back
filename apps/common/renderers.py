"""统一 JSON 渲染器：把成功响应包裹为 {code, message, data} 信封。"""
from rest_framework.renderers import JSONRenderer


class ApiRenderer(JSONRenderer):
    media_type = "application/json"
    format = "json"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get("response") if renderer_context else None
        status_code = response.status_code if response is not None else 200

        # 已是信封结构（来自 ApiResponse / 异常处理器），直接透传
        if isinstance(data, dict) and "code" in data and "message" in data:
            payload = data
        elif 200 <= status_code < 300:
            payload = {"code": 0, "message": "ok", "data": data}
        else:
            detail = data.get("detail", data) if isinstance(data, dict) else data
            payload = {"code": status_code, "message": str(detail), "data": None}

        return super().render(payload, accepted_media_type, renderer_context)
