"""基于角色的 DRF 权限。"""
from rest_framework.permissions import BasePermission


def has_role(*roles):
    """返回校验请求用户角色是否在指定集合内的权限类。

    用法：permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]
    """
    allowed = set(roles)

    class RolePermission(BasePermission):
        message = "当前角色无权执行该操作"

        def has_permission(self, request, view):
            user = request.user
            if not (user and user.is_authenticated):
                return False
            if user.is_superuser:
                return True
            return getattr(user, "role", None) in allowed

    return RolePermission
