"""账号管理视图：role 参数化的统一 User 管理。

文档核心设计：学生/教师/学校/区县/市级账号共用 User 模型，仅 role 字段不同。
一套 AccountViewSet + role 参数 + filter_by_scope 收敛数据范围覆盖 5 类账号。

接口矩阵（#28-#36）：
    #28 GET  账号列表 → 学校/区县/市州/省级
    #29 POST 创建账号 → 学校/区县/市州/省级
    #30 GET  账号详情 → 学校/区县/市州/省级
    #31 PUT  修改账号 → 学校/区县/市州/省级
    #32 DELETE 删除账号 → 学校/区县/市州/省级
    #33 POST {id}/reset-password/ → 学校/区县/市州/省级
    #34 POST batch-create/ → 学校
    #35 POST batch-import/ → 学校/省级
    #36 GET  {id}/materials/ → 教师/学校
"""
from django.db.models import Q
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse
from apps.common.scopes import filter_by_scope
from apps.common.views import BaseViewSet
from apps.users.models import User
from apps.users.serializers import (
    AccountManageSerializer,
    BatchCreateAccountSerializer,
    BatchImportAccountSerializer,
    UserSerializer,
)


class AccountViewSet(BaseViewSet):
    """统一账号管理（role 参数化 User 资源）。"""

    queryset = User.objects.filter(is_active=True)
    serializer_class = AccountManageSerializer
    search_fields = ["username", "real_name", "student_no", "phone"]
    ordering_fields = ["id", "date_joined"]

    # -------------------- 权限 --------------------

    def get_permissions(self):
        if self.action == "materials":
            return [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)()]
        if self.action == "batch_import":
            return [has_role(User.ROLE_SCHOOL, User.ROLE_PROVINCE)()]
        if self.action == "batch_create":
            return [has_role(User.ROLE_SCHOOL)()]
        return [has_role(User.ROLE_SCHOOL, User.ROLE_DISTRICT, User.ROLE_CITY, User.ROLE_PROVINCE)()]

    # -------------------- User 软删除用 is_active --------------------

    def perform_destroy(self, instance):
        """User 模型无 is_deleted 字段，用 is_active=False 做软删。"""
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    # -------------------- 数据隔离 --------------------

    def get_queryset(self):
        qs = super().get_queryset()
        # 按 role 过滤
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        # 按账号/学籍号过滤
        keyword = self.request.query_params.get("keyword")
        if keyword:
            qs = qs.filter(
                Q(username__icontains=keyword)
                | Q(student_no__icontains=keyword)
                | Q(real_name__icontains=keyword)
            )
        # 按 scope 收敛
        qs = filter_by_scope(qs, self.request.user, school_field="school", region_field="region")
        return qs

    # -------------------- #33 重置密码 --------------------

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        """后台重置指定账号密码。"""
        user = self.get_object()
        new_password = request.data.get("new_password", "123456")
        user.set_password(new_password)
        user.save()
        return ApiResponse({"new_password": new_password}, message="密码已重置")

    # -------------------- #34 批量创建 --------------------

    @action(detail=False, methods=["post"], url_path="batch-create")
    def batch_create(self, request):
        """批量创建账号（按前缀 + 序号生成）。"""
        ser = BatchCreateAccountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        school = data.get("school")
        region = data.get("region")
        count = data["count"]
        prefix = data["prefix"]
        role = data["role"]
        default_pwd = data.get("default_password", "123456")
        real_names = data.get("real_names") or []

        created = []
        for i in range(1, count + 1):
            username = f"{prefix}{i:03d}"
            real_name = real_names[i - 1] if i - 1 < len(real_names) else ""
            user, new = User.objects.get_or_create(
                username=username,
                defaults={
                    "role": role,
                    "school": school,
                    "region": region,
                    "real_name": real_name,
                },
            )
            if new:
                user.set_password(default_pwd)
                user.save()
                created.append(username)

        return ApiResponse(
            {"created": len(created), "usernames": created[:20]},
            message=f"批量创建完成，成功 {len(created)} 个",
        )

    # -------------------- #35 批量导入 --------------------

    @action(detail=False, methods=["post"], url_path="batch-import")
    def batch_import(self, request):
        """批量导入账号（接 Excel/CSV 解析后的 items 数组）。"""
        ser = BatchImportAccountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        role = ser.validated_data["role"]
        items = ser.validated_data["items"]

        created = 0
        skipped = 0
        errors = []
        for idx, item in enumerate(items):
            username = item.get("username")
            if not username:
                skipped += 1
                errors.append({"index": idx, "reason": "缺少 username"})
                continue
            if User.objects.filter(username=username, is_active=True).exists():
                skipped += 1
                continue
            user = User.objects.create(
                username=username,
                role=role,
                real_name=item.get("real_name", ""),
                phone=item.get("phone", ""),
                student_no=item.get("student_no", ""),
                school_id=item.get("school"),
                region_id=item.get("region"),
            )
            password = item.get("password", "123456")
            user.set_password(password)
            user.save()
            created += 1

        return ApiResponse(
            {"created": created, "skipped": skipped, "errors": errors[:10]},
            message=f"导入完成：成功 {created} 个，跳过 {skipped} 个",
        )

    # -------------------- #36 下载身份材料 --------------------

    @action(detail=True, methods=["get"], url_path="materials")
    def materials(self, request, pk=None):
        """查询学生身份材料（学籍号、学校、班级等汇总信息）。"""
        user = self.get_object()
        if user.role != User.ROLE_STUDENT:
            raise ApiException("仅学生有身份材料")

        # 查已通过的班级
        from apps.classroom.models import ClassStudent, APPROVED
        classes = ClassStudent.objects.filter(
            student=user, status=APPROVED, is_deleted=False,
        ).select_related("klass", "klass__school")

        class_list = [
            {
                "class_id": cs.klass.id,
                "class_name": cs.klass.name,
                "class_code": cs.klass.code,
                "school_name": cs.klass.school.name if cs.klass.school else "",
            }
            for cs in classes
        ]

        data = {
            "user_id": user.id,
            "username": user.username,
            "real_name": user.real_name,
            "student_no": user.student_no,
            "phone": user.phone,
            "school": user.school.name if user.school else "",
            "region": user.region.name if user.region else "",
            "classes": class_list,
        }
        return ApiResponse(data)
