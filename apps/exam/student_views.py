"""学生端结果接口（C 域 #14-#17）。

14. GET  /api/exam/my-scores/          查看我的成绩
15. GET  /api/exam/my-scores/curve/    成绩曲线
16. GET  /api/exam/my-growth/          个人成长曲线（音乐 / 美术）
17. POST /api/exam/extracurricular/    上传课外自主学习图片
"""
from datetime import datetime

from django.db.models import Q
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.classroom.models import APPROVED, ClassRoom, ClassStudent, ClassTeacher
from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse, ErrorCode
from apps.exam import services
from apps.exam.models import (
    AnswerSheet,
    ExtracurricularUpload,
    PerformanceScore,
    UploadedCertificate,
)
from apps.exam.serializers import ExtracurricularUploadSerializer, UploadedCertificateSerializer
from apps.users.models import User

CERT_ALLOWED_TYPES = {"image/jpeg", "image/png"}
CERT_MAX_SIZE = 5 * 1024 * 1024

SUBJECT_LABELS = {"music": "音乐", "art": "美术"}


def _course_subject(course):
    """把课程映射为 music / art。"""
    if course is None:
        return ""
    code = (course.code or "").strip().lower()
    if code in SUBJECT_LABELS:
        return code
    name = course.name or ""
    if "音乐" in name:
        return "music"
    if "美术" in name:
        return "art"
    return ""


def _exam_points(student):
    """测评成绩点（已提交答卷）。"""
    sheets = (
        AnswerSheet.objects.filter(student=student, is_submitted=True, is_deleted=False)
        .select_related("paper")
        .order_by("submitted_at")
    )
    points = []
    for sheet in sheets:
        total = float(sheet.paper.total_score or 0)
        score = float(sheet.total_score)
        points.append({
            "source": "exam",
            "title": sheet.paper.title,
            "subject": sheet.paper.subject,
            "subject_display": sheet.paper.get_subject_display(),
            "ptype": sheet.paper.ptype,
            "score": score,
            "total_score": total,
            "rate": round(score / total, 4) if total > 0 else 0,
            "date": sheet.submitted_at,
        })
    return points


def _performance_points(student):
    """平时表现评分点。"""
    records = (
        PerformanceScore.objects.filter(student=student, is_deleted=False)
        .select_related("course")
        .order_by("created_at")
    )
    points = []
    for item in records:
        subject = _course_subject(item.course)
        points.append({
            "source": "daily",
            "title": f"{item.course.name if item.course else '平时表现'}评分",
            "subject": subject,
            "subject_display": SUBJECT_LABELS.get(subject, ""),
            "ptype": "daily",
            "score": float(item.score),
            "total_score": 100,
            "rate": round(float(item.score) / 100, 4),
            "date": item.created_at,
        })
    return points


def _all_points(student):
    points = _exam_points(student) + _performance_points(student)
    points.sort(key=lambda p: p["date"] or 0)
    return points


def _point_payload(point):
    data = dict(point)
    if data.get("date") is not None:
        data["date"] = data["date"].strftime("%Y-%m-%d %H:%M:%S")
    return data


class MyScoresViewSet(viewsets.GenericViewSet):
    """学生端：我的成绩与成绩曲线。"""

    permission_classes = [has_role(User.ROLE_STUDENT)]

    def list(self, request):
        """我的成绩：测评成绩 + 平时表现评分 + 学科均分。"""
        exam_points = _exam_points(request.user)
        daily_points = _performance_points(request.user)
        subject_bucket = {}
        for point in exam_points + daily_points:
            key = point["subject"] or "other"
            subject_bucket.setdefault(key, []).append(point["rate"])

        by_subject = [
            {
                "subject": key,
                "subject_display": SUBJECT_LABELS.get(key, "其他"),
                "count": len(rates),
                "average_rate": round(sum(rates) / len(rates), 4),
            }
            for key, rates in subject_bucket.items()
        ]
        return ApiResponse(data={
            "exams": [_point_payload(p) for p in exam_points],
            "performances": [_point_payload(p) for p in daily_points],
            "by_subject": by_subject,
        })

    @action(detail=False, methods=["get"])
    def curve(self, request):
        """成绩曲线：按时间排序的全部成绩点（可得率 0-1）。"""
        points = _all_points(request.user)
        subject = request.query_params.get("subject")
        if subject:
            points = [p for p in points if p["subject"] == subject]
        return ApiResponse(data={
            "points": [_point_payload(p) for p in points],
            "total": len(points),
        })


class MyGrowthView(APIView):
    """GET /api/exam/my-growth/ 个人成长曲线（音乐 / 美术）。"""

    permission_classes = [has_role(User.ROLE_STUDENT)]

    def get(self, request):
        points = _all_points(request.user)
        series = {}
        for point in points:
            key = point["subject"] or "other"
            series.setdefault(key, []).append(_point_payload(point))

        data = [
            {
                "subject": key,
                "subject_display": SUBJECT_LABELS.get(key, "其他"),
                "count": len(items),
                "average_rate": round(sum(i["rate"] for i in items) / len(items), 4),
                "points": items,
            }
            for key, items in series.items()
        ]
        return ApiResponse(data={"series": data, "total": len(points)})


class ExtracurricularViewSet(viewsets.GenericViewSet):
    """学生课外自主学习上传。"""

    permission_classes = [has_role(User.ROLE_STUDENT)]
    serializer_class = ExtracurricularUploadSerializer

    def create(self, request):
        """POST /api/exam/extracurricular/ 上传课外学习图片（multipart）。"""
        image = request.FILES.get("image")
        if image is None:
            raise ApiException("请上传图片（字段名 image）", ErrorCode.INVALID_PARAM, 400)
        title = request.data.get("title") or "课外学习成果"
        record = ExtracurricularUpload.objects.create(
            student=request.user,
            title=title[:128],
            image=image,
            description=request.data.get("description", ""),
        )
        return ApiResponse(
            data={
                "id": record.id,
                "title": record.title,
                "image": request.build_absolute_uri(record.image.url) if record.image else "",
                "description": record.description,
                "created_at": record.created_at,
            },
            message="上传成功",
        )


class MyClassAssessmentView(APIView):
    """GET /api/exam/my-class/assessments/ 学生端：查看班级测评信息。

    查询参数：
    - subject：按学科过滤（music / art）
    - keyword：按测评名称 / 学科模糊搜索

    返回：所在班级信息、各测评的班级级成绩汇总、按学科汇总。
    """

    permission_classes = [has_role(User.ROLE_STUDENT)]

    def get(self, request):
        student = request.user
        class_ids = services.student_class_ids(student)
        classes = ClassRoom.objects.filter(id__in=class_ids, is_deleted=False)

        subject = request.query_params.get("subject")
        keyword = (request.query_params.get("keyword") or "").strip()

        publishes = services.available_publishes(student).select_related("paper")
        if subject:
            publishes = publishes.filter(paper__subject=subject)
        if keyword:
            publishes = publishes.filter(
                Q(paper__title__icontains=keyword) | Q(paper__subject__icontains=keyword)
            )

        # 所在班级内的全部学生（含本人）
        class_students = User.objects.filter(
            role=User.ROLE_STUDENT,
            class_memberships__klass_id__in=class_ids,
            class_memberships__status=services.APPROVED,
            class_memberships__is_deleted=False,
        ).distinct()
        class_size = class_students.count()

        items = []
        for publish in publishes:
            paper = publish.paper
            sheets = AnswerSheet.objects.filter(
                is_submitted=True, is_deleted=False, paper=paper, student__in=class_students
            )
            full = float(paper.total_score or 0)
            scores = [float(s.total_score) for s in sheets]
            participant = len(scores)
            average = round(sum(scores) / participant, 2) if scores else 0
            passed = sum(1 for s in scores if (s / full if full else 0) >= float(services.PASS_RATIO))
            items.append({
                "publish_id": publish.id,
                "paper_id": paper.id,
                "title": paper.title,
                "subject": paper.subject,
                "subject_display": paper.get_subject_display(),
                "ptype": paper.ptype,
                "ptype_display": paper.get_ptype_display(),
                "grade": paper.grade,
                "total_score": str(paper.total_score),
                "class_size": class_size,
                "participant_count": participant,
                "average_score": str(average),
                "pass_rate": round(passed / participant, 4) if participant else 0,
                "end_at": publish.end_at,
            })

        by_subject = {}
        for item in items:
            by_subject.setdefault(item["subject"], []).append(float(item["average_score"]))
        by_subject_list = [
            {
                "subject": key,
                "subject_display": SUBJECT_LABELS.get(key, "其他"),
                "assessment_count": len(vals),
                "average_score": str(round(sum(vals) / len(vals), 2)),
            }
            for key, vals in by_subject.items()
        ]

        return ApiResponse(data={
            "classes": [
                {
                    "id": c.id,
                    "name": c.name,
                    "code": c.code,
                    "school_name": c.school.name if c.school else "",
                }
                for c in classes
            ],
            "assessments": items,
            "by_subject": by_subject_list,
            "total": len(items),
        })


def _teacher_class_ids(teacher):
    """教师所带班级：已通过审核的科任班级 + 班主任班级。"""
    ids = set(
        ClassTeacher.objects.filter(
            teacher=teacher, status=APPROVED, is_deleted=False,
        ).values_list("klass_id", flat=True)
    )
    ids |= set(
        ClassRoom.objects.filter(head_teacher=teacher, is_deleted=False).values_list("id", flat=True)
    )
    return ids


def _teacher_student_ids(teacher):
    """教师可审核的学生：所带班级中已通过审核的学生。"""
    class_ids = _teacher_class_ids(teacher)
    if not class_ids:
        return []
    return list(
        ClassStudent.objects.filter(
            klass_id__in=class_ids, status=APPROVED, is_deleted=False,
        ).values_list("student_id", flat=True)
    )


class UploadedCertificateViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """学生上传证书：上传 / 我的列表 / 删除（学生），审核（教师）。"""

    queryset = UploadedCertificate.objects.all()
    serializer_class = UploadedCertificateSerializer

    def get_permissions(self):
        if self.action in ("list", "create", "destroy"):
            return [has_role(User.ROLE_STUDENT)()]
        return [has_role(User.ROLE_TEACHER)()]

    def get_queryset(self):
        qs = UploadedCertificate.objects.filter(is_deleted=False).select_related(
            "student", "reviewer"
        )
        user = self.request.user
        if user.role == User.ROLE_STUDENT:
            qs = qs.filter(student=user)
        elif user.role == User.ROLE_TEACHER:
            qs = qs.filter(student_id__in=_teacher_student_ids(user))
        return qs

    def _serialize(self, records):
        return UploadedCertificateSerializer(
            records, many=True, context={"request": self.request}
        ).data

    def list(self, request, *args, **kwargs):
        """我的上传证书列表（仅本人）。"""
        qs = self.get_queryset().order_by("-created_at")
        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return ApiResponse(data={"list": self._serialize(qs), "total": qs.count()})

    def create(self, request, *args, **kwargs):
        """上传证书（multipart/form-data，图片字段名 image）。"""
        image = request.FILES.get("image")
        if image is None:
            raise ApiException("请上传证书图片（字段名 image）", ErrorCode.INVALID_PARAM, 400)

        title = (request.data.get("title") or "").strip()
        if not title:
            raise ApiException("证书标题不能为空", ErrorCode.INVALID_PARAM, 400)

        if image.size > CERT_MAX_SIZE:
            raise ApiException("证书图片不能超过 5MB", ErrorCode.INVALID_PARAM, 400)

        content_type = (getattr(image, "content_type", "") or "").lower()
        if content_type not in CERT_ALLOWED_TYPES:
            raise ApiException("仅支持 JPG / PNG 格式的图片", ErrorCode.INVALID_PARAM, 400)

        obtained_at = None
        raw_date = (request.data.get("obtained_at") or "").strip()
        if raw_date:
            try:
                obtained_at = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                raise ApiException(
                    "获得日期格式应为 YYYY-MM-DD", ErrorCode.INVALID_PARAM, 400,
                )

        cert_type = request.data.get("cert_type") or UploadedCertificate.CERT_OTHER
        if cert_type not in dict(UploadedCertificate.CERT_TYPE_CHOICES):
            cert_type = UploadedCertificate.CERT_OTHER
        subject = request.data.get("subject") or UploadedCertificate.SUBJECT_OTHER
        if subject not in dict(UploadedCertificate.SUBJECT_CHOICES):
            subject = UploadedCertificate.SUBJECT_OTHER

        record = UploadedCertificate.objects.create(
            student=request.user,
            title=title[:128],
            cert_type=cert_type,
            subject=subject,
            issuer=(request.data.get("issuer") or "")[:128],
            obtained_at=obtained_at,
            image=image,
            note=request.data.get("note") or "",
        )
        data = UploadedCertificateSerializer(record, context={"request": request}).data
        return ApiResponse(data=data, message="上传成功", status=201)

    def destroy(self, request, *args, **kwargs):
        """软删除本人证书。"""
        record = self.get_object()
        record.is_deleted = True
        record.deleted_at = timezone.now()
        record.save(update_fields=["is_deleted", "deleted_at", "updated_at"])
        return ApiResponse(None, message="删除成功")

    @action(detail=False, methods=["get"], url_path="review")
    def review_list(self, request):
        """教师：待审核列表（仅本人所带班级学生）。"""
        qs = self.get_queryset().order_by("-created_at")
        status = request.query_params.get("status")
        if status:
            qs = qs.filter(status=status)
        return ApiResponse(data={"list": self._serialize(qs), "total": qs.count()})

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        """教师审核：非本人班级记录由 get_object 返回 404。"""
        record = self.get_object()
        approved = request.data.get("approved")
        passed = approved in (True, 1, "1", "true", "True")
        record.status = (
            UploadedCertificate.STATUS_APPROVED if passed else UploadedCertificate.STATUS_REJECTED
        )
        record.reviewer = request.user
        record.review_comment = request.data.get("comment") or ""
        record.reviewed_at = timezone.now()
        record.save(update_fields=["status", "reviewer", "review_comment", "reviewed_at", "updated_at"])
        data = UploadedCertificateSerializer(record, context={"request": request}).data
        return ApiResponse(data=data, message="审核通过" if passed else "已驳回")
