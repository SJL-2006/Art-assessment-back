"""学生端结果接口（C 域 #14-#17）。

14. GET  /api/exam/my-scores/          查看我的成绩
15. GET  /api/exam/my-scores/curve/    成绩曲线
16. GET  /api/exam/my-growth/          个人成长曲线（音乐 / 美术）
17. POST /api/exam/extracurricular/    上传课外自主学习图片
"""
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.classroom.models import ClassRoom
from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse, ErrorCode
from apps.exam import services
from apps.exam.models import AnswerSheet, ExtracurricularUpload, PerformanceScore
from apps.exam.serializers import ExtracurricularUploadSerializer
from apps.users.models import User

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
