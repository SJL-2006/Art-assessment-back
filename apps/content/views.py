"""内容模块：趣味课堂知识。

- 学生端：只读已发布内容（素质教育展示）。
- 维护端：题库管理员 / 省级管理员 CRUD。
"""
from apps.common.permissions import has_role
from apps.common.views import BaseViewSet
from apps.content.models import FunClassKnowledge
from apps.content.serializers import FunClassKnowledgeSerializer
from apps.users.models import User


class FunClassKnowledgeViewSet(BaseViewSet):
    """趣味课堂知识 CRUD（学生只读、管理员维护）。"""

    queryset = FunClassKnowledge.objects.all()
    serializer_class = FunClassKnowledgeSerializer
    search_fields = ["title"]
    ordering_fields = ["id", "sort"]

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [has_role(User.ROLE_STUDENT, User.ROLE_QB_ADMIN, User.ROLE_PROVINCE)()]
        return [has_role(User.ROLE_QB_ADMIN, User.ROLE_PROVINCE)()]

    def get_queryset(self):
        qs = super().get_queryset()
        # 学生只能看到已发布内容；管理员可见全部
        if self.request.user.role == User.ROLE_STUDENT:
            qs = qs.filter(is_published=True)
        subject = self.request.query_params.get("subject")
        if subject:
            qs = qs.filter(subject=subject)
        return qs
