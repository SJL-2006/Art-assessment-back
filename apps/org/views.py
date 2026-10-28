"""组织架构视图（行政区 Region + 学校 School）。

权限矩阵（对照接口文档）：
    Region：GET 学校/区县/市州/省级可查；POST/PUT 市州/省级可写；DELETE 仅省级
    School：区县/市州/省级 CRUD 全部
数据隔离：非省级角色自动通过 filter_by_scope 收敛查询范围。
"""
from rest_framework import permissions

from apps.common.permissions import has_role
from apps.common.scopes import filter_by_scope
from apps.common.views import BaseViewSet
from apps.org.models import Region, School
from apps.org.serializers import RegionSerializer, SchoolSerializer
from apps.users.models import User


class RegionViewSet(BaseViewSet):
    """行政区 CRUD。

    #7 GET  列表 → 学校/区县/市州/省级
    #8 POST 新增 → 市州/省级
    #9 GET  详情 → 学校/区县/市州/省级
    #10 PUT 修改 → 市州/省级
    #11 DELETE 删除 → 仅省级
    """

    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["id", "level"]

    def get_permissions(self):
        # 读操作：学校/区县/市州/省级都可
        if self.action in ("list", "retrieve"):
            return [has_role(User.ROLE_SCHOOL, User.ROLE_DISTRICT, User.ROLE_CITY, User.ROLE_PROVINCE)()]
        # 写操作：POST/PUT 市州/省级；DELETE 仅省级
        if self.action == "destroy":
            return [has_role(User.ROLE_PROVINCE)()]
        return [has_role(User.ROLE_CITY, User.ROLE_PROVINCE)()]

    def get_queryset(self):
        qs = super().get_queryset()
        # 按 level 查询参数过滤
        level = self.request.query_params.get("level")
        if level:
            qs = qs.filter(level=level)
        # 按当前用户 scope 收敛（非省级只能看自己范围）
        qs = filter_by_scope(qs, self.request.user, region_field=None, school_field=None)
        return qs


class SchoolViewSet(BaseViewSet):
    """学校 CRUD。

    #12-16 区县/市州/省级 CRUD 全部。
    """

    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["id"]

    def get_permissions(self):
        return [has_role(User.ROLE_DISTRICT, User.ROLE_CITY, User.ROLE_PROVINCE)()]

    def get_queryset(self):
        qs = super().get_queryset()
        # 按 region 查询参数过滤
        region = self.request.query_params.get("region")
        if region:
            qs = qs.filter(region_id=region)
        # 按是否市直属过滤
        directly = self.request.query_params.get("directly_affiliated")
        if directly is not None:
            qs = qs.filter(is_directly_affiliated=directly in ("1", "true", "True"))
        # 按当前用户 scope 收敛
        qs = filter_by_scope(qs, self.request.user, region_field="region", school_field=None)
        return qs
