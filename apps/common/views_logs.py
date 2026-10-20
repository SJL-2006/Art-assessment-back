"""系统操作日志查询（#37）。

只读接口，按模块/时间/方法过滤，仅省级和题库管理员可访问。
"""
from rest_framework import mixins, serializers, viewsets

from apps.common.models import OperationLog
from apps.common.permissions import has_role
from apps.common.pagination import StandardPagination
from apps.users.models import User


class LogSimpleSerializer(serializers.ModelSerializer):
    """操作日志最小序列化器。"""

    class Meta:
        model = OperationLog
        fields = "__all__"


class LogViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """操作日志列表查询。

    过滤参数：
        module     模块名（如 users、org、classroom、exam）
        method     HTTP 方法（GET/POST/PUT/DELETE）
        path       路径关键字模糊匹配
        start_time 起始时间（ISO 格式）
        end_time   结束时间（ISO 格式）
        user_id    操作人 ID
    """

    queryset = OperationLog.objects.all()
    serializer_class = LogSimpleSerializer
    pagination_class = StandardPagination
    permission_classes = [has_role(User.ROLE_PROVINCE, User.ROLE_QB_ADMIN)]

    def get_queryset(self):
        qs = OperationLog.objects.all()
        module = self.request.query_params.get("module")
        method = self.request.query_params.get("method")
        path = self.request.query_params.get("path")
        start_time = self.request.query_params.get("start_time")
        end_time = self.request.query_params.get("end_time")
        user_id = self.request.query_params.get("user_id")

        if module:
            qs = qs.filter(module=module)
        if method:
            qs = qs.filter(method=method)
        if path:
            qs = qs.filter(path__icontains=path)
        if start_time:
            qs = qs.filter(created_at__gte=start_time)
        if end_time:
            qs = qs.filter(created_at__lte=end_time)
        if user_id:
            qs = qs.filter(user_id=user_id)
        return qs
