"""班级视图。

接口矩阵（对照文档 #17-#27）：
    基础 CRUD：教师/学校
    join/quit/change：学生
    approve_student / approve_teacher：教师
    import_students：教师/学校
"""
import secrets
import string
from django.db.models import Case, Count, Exists, OuterRef, Q, Value, When
from django.db.models.fields import BooleanField
from django.utils import timezone
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action

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

# 班级编号字符集：去掉 0/O、1/I 等易混淆字符
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_class_code(length: int = 6) -> str:
    """生成未被占用的随机班级编号（如 C7Q4XM）。"""
    while True:
        code = "C" + "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))
        if not ClassRoom.objects.filter(code=code, is_deleted=False).exists():
            return code


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
        # 学生/教师通用只读 action（查我的班级、搜索班级）
        if self.action in ("my_class", "search"):
            return [permissions.IsAuthenticated()]
        # 学生专属 action
        if self.action in ("join", "quit", "change"):
            return [has_role(User.ROLE_STUDENT)()]
        # 教师专属 action
        if self.action in ("approve_student", "approve_teacher", "join_teacher", "remove_student"):
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
            # 给每个班级打标：当前用户是 head / 已通过的 subject
            subject_exists = ClassTeacher.objects.filter(
                klass=OuterRef("pk"),
                teacher=self.request.user,
                status=APPROVED,
                is_deleted=False,
            )
            qs = qs.annotate(
                is_my_head=Case(
                    When(head_teacher=self.request.user, then=Value(True)),
                    default=Value(False),
                    output_field=BooleanField(),
                ),
                is_my_subject=Exists(subject_exists),
            )
        # 学校：用 filter_by_scope 收敛到本校
        elif self.request.user.role == User.ROLE_SCHOOL:
            qs = filter_by_scope(qs, self.request.user, school_field="school", region_field=None)
        # 学生：仅能查看本校班级（加入前检索 / 查看详情）
        elif self.request.user.role == User.ROLE_STUDENT:
            qs = qs.filter(school_id=self.request.user.school_id)
        # 列表/详情统一注解已通过审核的学生数
        qs = qs.annotate(student_count=Count(
            "students",
            filter=Q(students__is_deleted=False, students__status=APPROVED),
            distinct=True,
        ))
        return qs

    def perform_create(self, serializer):
        """教师创建班级时自动把自己设为班主任；班级编号为空则随机生成。"""
        data = serializer.validated_data
        user = self.request.user
        extra = {}
        if not (data.get("code") or "").strip():
            extra["code"] = generate_class_code()
        if user.role == User.ROLE_TEACHER and not data.get("head_teacher"):
            extra["head_teacher"] = user
        serializer.save(**extra)

    # -------------------- 工具：绕过过滤取班级 --------------------

    def _get_raw_class(self, pk):
        try:
            klass = ClassRoom.objects.filter(is_deleted=False, pk=pk).first()
        except (ValueError, TypeError):
            klass = None
        if not klass:
            raise ApiException("班级不存在", code=404, status=404)
        return klass

    @staticmethod
    def _ensure_membership(klass, student):
        """取或恢复班级-学生关系：已软删除的行复活为待审核，避免命中 unique_together。"""
        cs = ClassStudent.objects.filter(klass=klass, student=student).first()
        if cs is None:
            return ClassStudent.objects.create(klass=klass, student=student, status=PENDING)
        if cs.is_deleted:
            cs.is_deleted = False
            cs.deleted_at = None
            cs.status = PENDING
            cs.save(update_fields=["is_deleted", "deleted_at", "status", "updated_at"])
        return cs

    # -------------------- 学生查询自己的班级 --------------------

    @action(detail=False, methods=["get"], url_path="my")
    def my_class(self, request):
        """学生查询自己已加入（审核通过）的班级列表（过滤已解散的）。"""
        memberships = (
            ClassStudent.objects.filter(
                student=request.user, is_deleted=False, status=APPROVED,
            ).select_related("klass")
        )
        klasses = [m.klass for m in memberships if m.klass and not m.klass.is_deleted]
        qs = ClassRoom.objects.filter(
            pk__in=[k.pk for k in klasses],
        ).annotate(student_count=Count(
            "students", filter=Q(students__is_deleted=False, students__status=APPROVED),
        ))
        return ApiResponse(ClassRoomSerializer(qs, many=True).data)

    # -------------------- 班级搜索（学生加入前查询） --------------------

    @action(detail=False, methods=["get"], url_path="search")
    def search(self, request):
        """按班级编号/名称模糊搜索本校班级（供学生加入前查询），最多返回 20 条。"""
        q = (request.query_params.get("q") or "").strip()
        if not q:
            return ApiResponse([])
        qs = (
            ClassRoom.objects.filter(is_deleted=False, school_id=request.user.school_id)
            .filter(Q(code__icontains=q) | Q(name__icontains=q))
            .annotate(student_count=Count(
                "students", filter=Q(students__is_deleted=False, students__status=APPROVED),
            ))
            .order_by("id")[:20]
        )
        return ApiResponse(ClassRoomSerializer(qs, many=True).data)

    # -------------------- #22 学生申请加入 --------------------

    @action(detail=True, methods=["post"], url_path="join")
    def join(self, request, pk=None):
        klass = self._get_raw_class(pk)
        if klass.school_id != request.user.school_id:
            raise ApiException("只能加入本校班级", code=403, status=403)
        cs = ClassStudent.objects.filter(klass=klass, student=request.user, is_deleted=False).first()
        if cs:
            if cs.status == APPROVED:
                raise ApiException("你已是该班级成员")
            if cs.status == PENDING:
                raise ApiException("已有待审核申请，请等待班主任处理")
            cs.status = PENDING
            cs.save(update_fields=["status", "updated_at"])
            return ApiResponse(ClassStudentSerializer(cs).data, message="已重新提交申请")

        cs = self._ensure_membership(klass, request.user)
        return ApiResponse(ClassStudentSerializer(cs).data, message="申请已提交", status=201)

    # -------------------- 教师申请加入班级（科任教师） --------------------

    @action(detail=True, methods=["post"], url_path="join-teacher")
    def join_teacher(self, request, pk=None):
        klass = self._get_raw_class(pk)
        if klass.head_teacher_id == request.user.id:
            raise ApiException("你已是该班级班主任")
        if klass.school_id != request.user.school_id:
            raise ApiException("只能加入本校班级", code=403, status=403)

        from apps.questionbank.models import Course
        course_id = request.data.get("course")
        if not course_id:
            raise ApiException("请选择任教学科", code=400, status=400)
        course = Course.objects.filter(pk=course_id, is_deleted=False).first()
        if course is None:
            raise ApiException("任教学科不存在", code=400, status=400)

        ct = ClassTeacher.objects.filter(klass=klass, teacher=request.user, is_deleted=False).first()
        if ct:
            if ct.status == APPROVED:
                raise ApiException("你已是该班级科任教师")
            if ct.status == PENDING:
                raise ApiException("已有待审核申请，请等待班主任处理")
            ct.status = PENDING
            ct.course = course
            ct.save(update_fields=["status", "course", "updated_at"])
            return ApiResponse(ClassTeacherSerializer(ct).data, message="已重新提交申请")

        # 复活已软删除的同课程关系，避免命中 unique_together(klass, teacher, course)
        soft = ClassTeacher.objects.filter(klass=klass, teacher=request.user, course=course).first()
        if soft is not None:
            soft.is_deleted = False
            soft.deleted_at = None
            soft.status = PENDING
            soft.save(update_fields=["is_deleted", "deleted_at", "status", "updated_at"])
            return ApiResponse(ClassTeacherSerializer(soft).data, message="已重新提交申请")

        ct = ClassTeacher.objects.create(
            klass=klass, teacher=request.user, course=course, status=PENDING,
        )
        return ApiResponse(ClassTeacherSerializer(ct).data, message="科任教师申请已提交", status=201)

    # -------------------- #23 学生退出 --------------------

    @action(detail=True, methods=["post"], url_path="quit")
    def quit(self, request, pk=None):
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
        ser = ChangeClassSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        target_id = ser.validated_data["target_class_id"]

        klass = self._get_raw_class(pk)
        current = ClassStudent.objects.filter(
            klass=klass, student=request.user, is_deleted=False, status=APPROVED,
        ).first()
        if not current:
            raise ApiException("你不是该班级成员，无法换班")
        current.is_deleted = True
        current.deleted_at = timezone.now()
        current.save(update_fields=["is_deleted", "deleted_at", "updated_at"])

        target = ClassRoom.objects.filter(id=target_id, is_deleted=False).first()
        if not target:
            raise ApiException("目标班级不存在")
        if target.school_id != request.user.school_id:
            raise ApiException("只能转入本校班级", code=403, status=403)
        cs = self._ensure_membership(target, request.user)
        return ApiResponse(ClassStudentSerializer(cs).data, message="换班申请已提交", status=201)

    # -------------------- #25 教师审核学生申请 --------------------

    @action(detail=True, methods=["post"], url_path=r"students/(?P<sid>[^/.]+)/approve")
    def approve_student(self, request, pk=None, sid=None):
        klass = self._get_raw_class(pk)
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

    # -------------------- 把学生移出班级 --------------------

    @action(detail=True, methods=["post"], url_path=r"students/(?P<sid>[^/.]+)/remove")
    def remove_student(self, request, pk=None, sid=None):
        """把已入班的学生移出班级——仅班级班主任有权限（软删除）。"""
        klass = self._get_raw_class(pk)
        if klass.head_teacher_id != request.user.id:
            raise ApiException("只有班主任能把学生移出班级", code=403, status=403)

        cs = ClassStudent.objects.filter(klass=klass, student_id=sid, is_deleted=False).first()
        if not cs:
            raise ApiException("该学生不在此班级中")

        cs.is_deleted = True
        cs.deleted_at = timezone.now()
        cs.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        return ApiResponse(None, message="已将该学生移出班级")

    # -------------------- #26 班主任审核科任教师 --------------------

    @action(detail=True, methods=["post"], url_path=r"teachers/(?P<tid>[^/.]+)/approve")
    def approve_teacher(self, request, pk=None, tid=None):
        klass = self._get_raw_class(pk)
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
        klass = self._get_raw_class(pk)
        # 越权保护：教师只能向自己所带班级导入，学校只能向本校班级导入
        if request.user.role == User.ROLE_TEACHER:
            is_head = klass.head_teacher_id == request.user.id
            is_subject = ClassTeacher.objects.filter(
                klass=klass, teacher=request.user, status=APPROVED, is_deleted=False,
            ).exists()
            if not (is_head or is_subject):
                raise ApiException("只能向自己所带班级导入学生", code=403, status=403)
        elif request.user.role == User.ROLE_SCHOOL and klass.school_id != request.user.school_id:
            raise ApiException("只能向本校班级导入学生", code=403, status=403)

        ser = ImportStudentsSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        student_ids = ser.validated_data.get("student_ids") or []
        student_nos = ser.validated_data.get("student_nos") or []
        usernames = ser.validated_data.get("usernames") or []

        if not student_ids and not student_nos and not usernames:
            raise ApiException("student_ids、student_nos、usernames 至少传一个")

        users = User.objects.filter(
            Q(id__in=student_ids) | Q(student_no__in=student_nos) | Q(username__in=usernames),
            is_active=True,
        ).distinct()
        created = 0
        skipped = 0
        for user in users:
            if user.role != User.ROLE_STUDENT:
                skipped += 1
                continue
            cs = ClassStudent.objects.filter(klass=klass, student=user).first()
            if cs is None:
                ClassStudent.objects.create(klass=klass, student=user, status=APPROVED)
                created += 1
            elif cs.is_deleted:
                # 复活已软删除的关系（例如退出后又重新导入），避免命中 unique_together
                cs.is_deleted = False
                cs.deleted_at = None
                cs.status = APPROVED
                cs.save(update_fields=["is_deleted", "deleted_at", "status", "updated_at"])
                created += 1
            else:
                skipped += 1

        return ApiResponse(
            {"created": created, "skipped": skipped, "total": users.count()},
            message=f"导入完成：成功 {created} 人，跳过 {skipped} 人",
        )


class ClassStudentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """班级-学生关系只读接口。"""
    queryset = ClassStudent.objects.filter(is_deleted=False)
    serializer_class = ClassStudentSerializer
    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL, User.ROLE_STUDENT)]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # 数据隔离：学生仅看本人、教师仅看所带班级、学校仅看本校
        if user.role == User.ROLE_STUDENT:
            qs = qs.filter(student=user)
        elif user.role == User.ROLE_TEACHER:
            class_ids = ClassRoom.objects.filter(
                Q(head_teacher=user)
                | Q(teachers__teacher=user, teachers__status=APPROVED, teachers__is_deleted=False),
                is_deleted=False,
            ).values_list("id", flat=True)
            qs = qs.filter(klass_id__in=class_ids)
        elif user.role == User.ROLE_SCHOOL:
            qs = qs.filter(klass__school_id=user.school_id)

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        else:
            qs = qs.filter(status=APPROVED)
        klass = self.request.query_params.get("class")
        if klass:
            qs = qs.filter(klass_id=klass)
        return qs


class ClassTeacherViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """班级-教师关系只读接口。"""
    queryset = ClassTeacher.objects.filter(is_deleted=False)
    serializer_class = ClassTeacherSerializer
    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        # 数据隔离：教师仅看所带班级、学校仅看本校
        if user.role == User.ROLE_TEACHER:
            class_ids = ClassRoom.objects.filter(
                Q(head_teacher=user)
                | Q(teachers__teacher=user, teachers__status=APPROVED, teachers__is_deleted=False),
                is_deleted=False,
            ).values_list("id", flat=True)
            qs = qs.filter(klass_id__in=class_ids)
        elif user.role == User.ROLE_SCHOOL:
            qs = qs.filter(klass__school_id=user.school_id)

        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        else:
            qs = qs.filter(status=APPROVED)
        klass = self.request.query_params.get("class")
        if klass:
            qs = qs.filter(klass_id=klass)
        return qs
