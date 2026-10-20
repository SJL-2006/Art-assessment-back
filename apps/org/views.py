from apps.common.views import BaseViewSet
from apps.org.models import Region, School
from apps.org.serializers import RegionSerializer, SchoolSerializer


class RegionViewSet(BaseViewSet):
    """行政区划 CRUD。"""
    queryset = Region.objects.all()
    serializer_class = RegionSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["id", "level"]

    def get_queryset(self):
        qs = super().get_queryset()
        level = self.request.query_params.get("level")
        if level:
            qs = qs.filter(level=level)
        return qs


class SchoolViewSet(BaseViewSet):
    """学校 CRUD。"""
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["id"]

    def get_queryset(self):
        qs = super().get_queryset()
        region = self.request.query_params.get("region")
        if region:
            qs = qs.filter(region_id=region)
        return qs
