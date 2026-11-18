"""全局搜索接口：跨班级/试卷/学生三类资源。

前端顶部搜索框调这一个接口，返回分组好的结果。
"""
from rest_framework.views import APIView

from apps.classroom.models import ClassRoom
from apps.common.permissions import has_role
from apps.common.response import ApiResponse
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

        # 权限过滤：教师只能搜自己所带班级相关的，学校 admin 可以搜全校
        is_teacher = has_role(user, User.ROLE_TEACHER)
        # 管理员角色：学校 / 区县 / 市 / 省 / 题库管理员 都视为可搜全校
        is_admin = has_role(
            user,
            User.ROLE_SCHOOL, User.ROLE_DISTRICT, User.ROLE_CITY,
            User.ROLE_PROVINCE, User.ROLE_QB_ADMIN,
        )

        if "classroom" in scopes:
            from django.db.models import Q
            qs = ClassRoom.objects.filter(
                is_deleted=False,
                name__icontains=q,
            ).order_by("name")
            if is_teacher:
                # 教师只能搜自己带的班级（班主任 or 科任）
                # teachers 是 ClassTeacher related_name，中间表再通过 teacher 关联到 User
                qs = qs.filter(
                    Q(head_teacher=user) | Q(teachers__teacher=user),
                ).distinct()
            result["classrooms"] = [
                {
                    "id": c.id,
                    "name": c.name,
                    "code": c.code,
                    "grade": c.grade or "",
                    "school_name": c.school.name if c.school else "",
                    "student_count": c.students.filter(is_deleted=False, status="approved").count(),
                    "head_teacher_name": c.head_teacher.real_name or c.head_teacher.username if c.head_teacher else "",
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
            # 教师只看自己创建的 / 所带班级涉及的
            if is_teacher:
                qs = qs.filter(creator=user)
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
                }
                for p in qs[:30]
            ]

        if "student" in scopes and (is_teacher or is_admin):
            # 教师/学校可以搜学生
            from apps.classroom.models import ClassStudent
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
            if is_teacher:
                # 限制为教师所带班级中的学生
                from django.db.models import Q
                class_ids = list(
                    ClassRoom.objects.filter(
                        Q(head_teacher=user) | Q(teachers__teacher=user),
                        is_deleted=False,
                    ).values_list("id", flat=True).distinct()
                )
                if class_ids:
                    allowed_stu_ids = set(
                        ClassStudent.objects.filter(
                            klass_id__in=class_ids,
                            status="approved",
                            is_deleted=False,
                        ).values_list("student_id", flat=True)
                    )
                    stu_qs = stu_qs.filter(id__in=allowed_stu_ids)
                else:
                    stu_qs = User.objects.none()
            result["students"] = [
                {
                    "id": s.id,
                    "name": s.real_name or s.username,
                    "username": s.username,
                    "student_no": s.student_no or "",
                    "grade": s.grade or "",
                    "class_names": list(
                        ClassRoom.objects.filter(
                            students__student=s,
                            students__status="approved",
                            students__is_deleted=False,
                            is_deleted=False,
                        ).values_list("name", flat=True)
                    ),
                }
                for s in stu_qs[:30]
            ]

        result["counts"] = {k: len(v) for k, v in result.items() if k != "counts"}
        result["total"] = sum(result["counts"].values())
        return ApiResponse(data=result)
