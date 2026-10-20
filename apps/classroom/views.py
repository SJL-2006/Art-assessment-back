"""班级视图。

接口矩阵（对照文档 #17-#27）：
    基础 CRUD：教师/学校
    join/quit/change：学生
    approve_student / approve_teacher：教师
    import_students：教师/学校
"""
from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.classroom.models import (
    PENDING, APPROVED, REJECTED,
    ClassRoom, ClassStudent, ClassTeacher,
)
from apps.classroom.serializers import (
    ApproveResultSerializer,
    ChangeClassSerializer,
    ClassRoomSerializer,
    ClassStudentSerializer,
    ClassTeacherSerializer,
    ImportStudentsSerializer,
    JoinClassSerializer,
)
from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse
from apps.common.scopes import filter_by_scope
from apps.common.views import BaseViewSet
from apps.users.models import User


class ClassRoomViewSet(BaseViewSet):
    """班级 CRUD + 业务操作。

    #17 GET  列表 → 教师/学校（学生通过 join 等 action 间接访问）
    #18 POST 创建 → 教师/学校
    #19 GET  详情 → 学生/教师/学校
    #20 PUT  修改 → 教师/学校
    #21 DELETE 解散 → 教师/学校
    #22 POST {id}/join/ → 学生申请加入
    #23 POST {id}/quit/ → 学生退出班级
    #24 POST {id}/change/ → 学生申请换班
    #25 POST {id}/students/{sid}/approve/ → 教师审核学生申请
    #26 POST {id}/teachers/{tid}/approve/ → 班主任审核科任教师
    #27 POST {id}/students/import/ → 教师/学校批量导入学生
    """

    queryset = ClassRoom.objects.all()
    serializer_class = ClassRoomSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["id"]

    # -------------------- 权限 --------------------

    def get_permissions(self):
        # 详情查看：学生也能看
        if self.action == "retrieve":
            return [permissions.IsAuthenticated()]
        # 学生专属 action
        if self.action in ("join", "quit", "change"):
            return [has_role(User.ROLE_STUDENT)()]
        # 教师专属 action
        if self.action in ("approve_student", "approve_teacher", "join_teacher"):
            return [has_role(User.ROLE_TEACHER)()]
        # 教师/学校都可
        if self.action in ("list", "create", "update", "partial_update", "destroy", "import_students"):
            return [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)()]
        return [permissions.IsAuthenticated()]

    # -------------------- 数据隔离 --------------------

    def get_queryset(self):
        qs = super().get_queryset()
        school = self.request.query_params.get("school")
        if school:
            qs = qs.filter(school_id=school)
        # 教师：只看自己所在班级（班主任 + 科任教师）
        if self.request.user.role == User.ROLE_TEACHER:
            qs = qs.filter(
                Q(head_teacher=self.request.user)
                | Q(teachers__teacher=self.request.user, teachers__status=APPROVED)
            ).distinct()
        # 学校：用 filter_by_scope 收敛到本校
        elif self.request.user.role == User.ROLE_SCHOOL:
            qs = filter_by_scope(qs, self.request.user, school_field="school", region_field=None)
        return qs

    def perform_create(self, serializer):
        """教师创建班级时自动把自己设为班主任（head_teacher 为空时）。"""
        data = serializer.validated_data
        user = self.request.user
        if user.role == User.ROLE_TEACHER and not data.get("head_teacher"):
            serializer.save(head_teacher=user)
        else:
            serializer.save()

    # -------------------- 工具：绕过过滤取班级 --------------------

    def _get_raw_class(self, pk):
        """绕过 get_queryset 的角色过滤，直接取 ClassRoom（供班级内业务操作使用）。"""
        try:
            klass = ClassRoom.objects.filter(is_deleted=False, pk=pk).first()
        except (ValueError, TypeError):
            klass = None
        if not klass:
            raise ApiException("班级不存在", code=404, status=404)
        return klass

    # -------------------- #22 学生申请加入 --------------------

    @action(detail=True, methods=["post"], url_path="join")
    def join(self, request, pk=None):
        """学生申请加入指定班级（写入一条 pending 状态的 ClassStudent）。"""
        klass = self._get_raw_class(pk)
        # 是否已存在未删除的 membership
        cs = ClassStudent.objects.filter(klass=klass, student=request.user, is_deleted=False).first()
        if cs:
            if cs.status == APPROVED:
                raise ApiException("你已是该班级成员")
            if cs.status == PENDING:
                raise ApiException("已有待审核申请，请等待班主任处理")
            # rejected → 允许重新申请
            cs.status = PENDING
            cs.save(update_fields=["status", "updated_at"])
            return ApiResponse(ClassStudentSerializer(cs).data, message="已重新提交申请")

        cs = ClassStudent.objects.create(klass=klass, student=request.user, status=PENDING)
        return ApiResponse(ClassStudentSerializer(cs).data, message="申请已提交", status=201)

    # -------------------- 教师申请加入班级（科任教师） --------------------

    @action(detail=True, methods=["post"], url_path="join-teacher")
    def join_teacher(self, request, pk=None):
        """教师申请加入指定班级担任科任教师（写入 pending 状态的 ClassTeacher）。

        对应接口文档 #26 审核科任教师申请的前置提交接口。
        """
        klass = self._get_raw_class(pk)
        # 不能申请自己当班主任的班级
        if klass.head_teacher_id == request.user.id:
            raise ApiException("你已是该班级班主任")
        # 同一学校才能加入
        if klass.school_id != request.user.school_id:
            raise ApiException("只能加入本校班级", code=403, status=403)

        ct = ClassTeacher.objects.filter(klass=klass, teacher=request.user, is_deleted=False).first()
        if ct:
            if ct.status == APPROVED:
                raise ApiException("你已是该班级科任教师")
            if ct.status == PENDING:
                raise ApiException("已有待审核申请，请等待班主任处理")
            # rejected → 允许重新申请
            ct.status = PENDING
            ct.save(update_fields=["status", "updated_at"])
            return ApiResponse(ClassTeacherSerializer(ct).data, message="已重新提交申请")

        ct = ClassTeacher.objects.create(klass=klass, teacher=request.user, status=PENDING)
        return ApiResponse(ClassTeacherSerializer(ct).data, message="科任教师申请已提交", status=201)

    # -------------------- #23 学生退出 --------------------

    @action(detail=True, methods=["post"], url_path="quit")
    def quit(self, request, pk=None):
        """学生退出班级（软删除 ClassStudent 记录）。"""
        klass = self._get_raw_class(pk)
        cs = ClassStudent.objects.filter(klass=klass, student=request.user, is_deleted=False).first()
        if not cs:
            raise ApiException("你不是该班级成员")
        cs.is_deleted = True
        cs.deleted_at = timezone.now()
        cs.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        return ApiResponse(None, message="已退出班级")

    # -------------------- #24 学生换班 --------------------

    @action(detail=True, methods=["post"], url_path="change")
    def change(self, request, pk=None):
        """学生申请从当前班级换到目标班级。"""
        ser = ChangeClassSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        target_id = ser.validated_data["target_class_id"]

        # 先退出当前班级
        klass = self._get_raw_class(pk)
        current = ClassStudent.objects.filter(
            klass=klass, student=request.user, is_deleted=False, status=APPROVED,
        ).first()
        if not current:
            raise ApiException("你不是该班级成员，无法换班")
        current.is_deleted = True
        current.deleted_at = timezone.now()
        current.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

        # 在目标班级提交申请
        target = ClassRoom.objects.filter(id=target_id, is_deleted=False).first()
        if not target:
            raise ApiException("目标班级不存在")
        cs = ClassStudent.objects.create(klass=target, student=request.user, status=PENDING)
        return ApiResponse(ClassStudentSerializer(cs).data, message="换班申请已提交", status=201)

    # -------------------- #25 教师审核学生申请 --------------------

    @action(detail=True, methods=["post"], url_path=r"students/(?P<sid>[^/.]+)/approve")
    def approve_student(self, request, pk=None, sid=None):
        """班主任/教师审核某学生的入班申请。"""
        klass = self._get_raw_class(pk)
        # 权限：班主任 或 已通过的科任教师 才能审核
        is_head = klass.head_teacher_id == request.user.id
        is_teacher = ClassTeacher.objects.filter(
            klass=klass, teacher=request.user, status=APPROVED, is_deleted=False,
        ).exists()
        if not (is_head or is_teacher):
            raise ApiException("只有该班级的班主任或科任教师能审核", code=403, status=403)
        ser = ApproveResultSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        approved = ser.validated_data["approved"]

        cs = ClassStudent.objects.filter(klass=klass, student_id=sid, is_deleted=False).first()
        if not cs:
            raise ApiException("未找到该学生的申请记录")
        if cs.status != PENDING:
            raise ApiException("该申请已处理过")

        cs.status = APPROVED if approved else REJECTED
        cs.save(update_fields=["status", "updated_at"])
        msg = "审核通过" if approved else "已拒绝"
        return ApiResponse(ClassStudentSerializer(cs).data, message=msg)

    # -------------------- #26 班主任审核科任教师 --------------------

    @action(detail=True, methods=["post"], url_path=r"teachers/(?P<tid>[^/.]+)/approve")
    def approve_teacher(self, request, pk=None, tid=None):
        """班主任审核科任教师加入申请。"""
        klass = self._get_raw_class(pk)
        # 只有班主任能审核
        if klass.head_teacher_id != request.user.id:
            raise ApiException("只有班主任能审核科任教师", code=403, status=403)

        ser = ApproveResultSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        approved = ser.validated_data["approved"]

        ct = ClassTeacher.objects.filter(klass=klass, teacher_id=tid, is_deleted=False).first()
        if not ct:
            raise ApiException("未找到该教师的申请记录")
        if ct.status != PENDING:
            raise ApiException("该申请已处理过")

        ct.status = APPROVED if approved else REJECTED
        ct.save(update_fields=["status", "updated_at"])
        msg = "已通过科任教师申请" if approved else "已拒绝科任教师申请"
        return ApiResponse(ClassTeacherSerializer(ct).data, message=msg)

    # -------------------- #27 批量导入学生 --------------------

    @action(detail=True, methods=["post"], url_path="students/import")
    def import_students(self, request, pk=None):
        """批量导入学生入班（通过学生 ID 或学籍号）。"""
        klass = self._get_raw_class(pk)
        ser = ImportStudentsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        student_ids = ser.validated_data.get("student_ids") or []
        student_nos = ser.validated_data.get("student_nos") or []

        if not student_ids and not student_nos:
            raise ApiException("student_ids 和 student_nos 至少传一个")

        users = User.objects.filter(Q(id__in=student_ids) | Q(student_no__in=student_nos), is_active=True)
        created = 0
        skipped = 0
        for user in users:
            if user.role != User.ROLE_STUDENT:
                skipped += 1
                continue
            _, new = ClassStudent.objects.get_or_create(
                klass=klass, student=user, is_deleted=False,
                defaults={"status": APPROVED},
            )
            if new:
                created += 1
            else:
                skipped += 1

        return ApiResponse(
            {"created": created, "skipped": skipped, "total": users.count()},
            message=f"导入完成：成功 {created} 人，跳过 {skipped} 人",
        )


class ClassStudentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """班级-学生关系只读接口（供前端查询班级学生列表用）。"""

    queryset = ClassStudent.objects.filter(is_deleted=False, status=APPROVED)
    serializer_class = ClassStudentSerializer
    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL, User.ROLE_STUDENT)]

    def get_queryset(self):
        qs = super().get_queryset()
        klass = self.request.query_params.get("class")
        if klass:
            qs = qs.filter(klass_id=klass)
        return qs


class ClassTeacherViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """班级-教师关系只读接口。"""

    queryset = ClassTeacher.objects.filter(is_deleted=False, status=APPROVED)
    serializer_class = ClassTeacherSerializer
    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get_queryset(self):
        qs = super().get_queryset()
        klass = self.request.query_params.get("class")
        if klass:
            qs = qs.filter(klass_id=klass)
        return qs
