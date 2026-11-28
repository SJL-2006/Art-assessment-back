"""全局搜索接口：跨班级/试卷/学生三类资源。

前端顶部搜索框调这一个接口，返回分组好的结果。
"""
from django.db.models import Q
from rest_framework.views import APIView

from apps.classroom.models import APPROVED, ClassRoom, ClassStudent
from apps.common.permissions import has_role
from apps.common.response import ApiResponse
from apps.exam import services
from apps.exam.models import Paper
from apps.users.models import User


class GlobalSearchView(APIView):
    """GET /api/search/?q=xxx&scope=all

    查询参数：
    - q: 搜索关键词（必填）
    - scope: all(默认) | classroom | paper | student 可多选逗号分隔，如 scope=classroom,paper
    - subject: 可选，music / art，限定试卷学科

    返回：{ classrooms: [...], papers: [...], students: [...] }
    每类都最多返回 30 条，避免大结果集。
    """

    permission_classes = [
        has_role(
            User.ROLE_STUDENT, User.ROLE_TEACHER, User.ROLE_SCHOOL,
            User.ROLE_DISTRICT, User.ROLE_CITY, User.ROLE_PROVINCE,
            User.ROLE_QB_ADMIN,
        )
    ]

    def get(self, request):
        user = request.user
        if not user or not user.is_authenticated:
            return ApiResponse(message="未登录", status=401)

        q = (request.query_params.get("q") or "").strip()
        if not q:
            return ApiResponse(data={"classrooms": [], "papers": [], "students": []})

        scope_raw = (request.query_params.get("scope") or "all").lower()
        scopes = {s.strip() for s in scope_raw.split(",") if s.strip()}
        if "all" in scopes or not scopes:
            scopes = {"classroom", "paper", "student"}

        subject = request.query_params.get("subject")

        result = {"classrooms": [], "papers": [], "students": []}

        # 权限判定：按真实角色判断（has_role 返回的是权限类，不能当布尔值用）
        is_teacher = user.role == User.ROLE_TEACHER
        is_admin = user.role in (
            User.ROLE_SCHOOL, User.ROLE_DISTRICT, User.ROLE_CITY,
            User.ROLE_PROVINCE, User.ROLE_QB_ADMIN,
        )

        def scope_classrooms(qs):
            if user.is_superuser or user.role in (User.ROLE_PROVINCE, User.ROLE_QB_ADMIN):
                return qs
            if user.role == User.ROLE_CITY:
                return qs.filter(school__region_id__in=services.visible_region_ids(user))
            if user.role == User.ROLE_DISTRICT:
                return qs.filter(school__region_id=user.region_id)
            if user.role == User.ROLE_SCHOOL:
                return qs.filter(school_id=user.school_id)
            if user.role == User.ROLE_STUDENT:
                # 学生：自己所在的班级
                return qs.filter(
                    students__student=user,
                    students__status=APPROVED,
                    students__is_deleted=False,
                    is_deleted=False,
                ).distinct()
            # 教师：自己带的班级（班主任 or 科任）
            return qs.filter(Q(head_teacher=user) | Q(teachers__teacher=user)).distinct()

        def scope_papers(qs):
            if user.is_superuser or user.role in (User.ROLE_PROVINCE, User.ROLE_QB_ADMIN):
                return qs
            if user.role == User.ROLE_CITY:
                return qs.filter(creator__school__region_id__in=services.visible_region_ids(user))
            if user.role == User.ROLE_DISTRICT:
                return qs.filter(creator__school__region_id=user.region_id)
            if user.role == User.ROLE_SCHOOL:
                return qs.filter(creator__school_id=user.school_id)
            if user.role == User.ROLE_STUDENT:
                # 学生：看到同校所有已发布的试卷（兼容 creator 未挂 school 的历史数据）
                return qs.filter(status=Paper.STATUS_PUBLISHED).filter(
                    Q(creator__school_id=user.school_id) | Q(creator__school_id__isnull=True)
                )
            # 教师：自己创建的
            return qs.filter(creator=user)

        def scope_students(qs):
            if user.is_superuser or user.role in (User.ROLE_PROVINCE, User.ROLE_QB_ADMIN):
                return qs
            if user.role == User.ROLE_CITY:
                return qs.filter(school__region_id__in=services.visible_region_ids(user))
            if user.role == User.ROLE_DISTRICT:
                return qs.filter(school__region_id=user.region_id)
            if user.role == User.ROLE_SCHOOL:
                return qs.filter(school_id=user.school_id)
            # 教师 → 所带班级中已通过审核的学生
            class_ids = list(
                ClassRoom.objects.filter(
                    Q(head_teacher=user) | Q(teachers__teacher=user),
                    is_deleted=False,
                ).values_list("id", flat=True).distinct()
            )
            if not class_ids:
                return User.objects.none()
            allowed_ids = set(
                ClassStudent.objects.filter(
                    klass_id__in=class_ids, status=APPROVED, is_deleted=False,
                ).values_list("student_id", flat=True)
            )
            return qs.filter(id__in=allowed_ids)

        if "classroom" in scopes:
            qs = ClassRoom.objects.filter(
                is_deleted=False,
                name__icontains=q,
            ).order_by("name")
            qs = scope_classrooms(qs)
            result["classrooms"] = [
                {
                    "id": c.id,
                    "name": c.name,
                    "code": c.code,
                    "grade": c.grade or "",
                    "school_name": c.school.name if c.school else "",
                    "student_count": c.students.filter(is_deleted=False, status=APPROVED).count(),
                    "head_teacher_name": c.head_teacher.real_name or c.head_teacher.username if c.head_teacher else "",
                    "target": f"/classroom/{c.id}",
                }
                for c in qs[:30]
            ]

        if "paper" in scopes:
            qs = Paper.objects.filter(
                is_deleted=False,
                title__icontains=q,
            ).select_related("creator").order_by("-created_at")
            if subject in ("music", "art"):
                qs = qs.filter(subject=subject)
            qs = scope_papers(qs)
            result["papers"] = [
                {
                    "id": p.id,
                    "title": p.title,
                    "subject": p.subject,
                    "subject_display": p.get_subject_display(),
                    "ptype": p.ptype,
                    "ptype_display": p.get_ptype_display(),
                    "grade": p.grade or "",
                    "total_score": float(p.total_score or 0),
                    "status": p.status,
                    "question_count": p.paper_questions.count(),
                    "creator_name": p.creator.real_name or p.creator.username if p.creator else "",
                    "target": f"/exam/papers/{p.id}",
                }
                for p in qs[:30]
            ]

        if "student" in scopes and (is_teacher or is_admin):
            stu_qs = User.objects.filter(
                role=User.ROLE_STUDENT,
            ).filter(
                username__icontains=q,
            ) | User.objects.filter(
                role=User.ROLE_STUDENT,
                real_name__icontains=q,
            ) | User.objects.filter(
                role=User.ROLE_STUDENT,
                student_no__icontains=q,
            )
            stu_qs = stu_qs.distinct().order_by("real_name", "username")
            stu_qs = scope_students(stu_qs)
            result["students"] = [
                {
                    "id": s.id,
                    "name": s.real_name or s.username,
                    "username": s.username,
                    "student_no": s.student_no or "",
                    "class_names": list(
                        ClassRoom.objects.filter(
                            students__student=s,
                            students__status=APPROVED,
                            students__is_deleted=False,
                            is_deleted=False,
                        ).values_list("name", flat=True)
                    ),
                    "target": f"/exam/students/{s.id}/scores",
                }
                for s in stu_qs[:30]
            ]

        result["counts"] = {k: len(v) for k, v in result.items() if k != "counts"}
        result["total"] = sum(result["counts"].values())
        return ApiResponse(data=result)
