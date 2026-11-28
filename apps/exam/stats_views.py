"""数据统计接口（C 域 #18-#20）。

18. GET /api/exam/stats/assessment/                测评数据统计（按学校/地区/市州/年级/学科）
19. GET /api/exam/stats/assessment/export/         统计导出 Excel
20. GET /api/exam/stats/participation/export/      测评参与率导出（省级）
"""
from django.db.models import Count
from rest_framework.views import APIView

from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse, ErrorCode
from apps.exam import services
from apps.exam.exports import xlsx_response
from apps.exam.models import AnswerSheet
from apps.users.models import User

STATS_ROLES = has_role(
    User.ROLE_SCHOOL, User.ROLE_DISTRICT, User.ROLE_CITY, User.ROLE_PROVINCE
)


def _scoped_students(request):
    """按账号层级 + 查询参数收敛学生范围（同时作为参与率分母）。"""
    user = request.user
    params = request.query_params
    students = services.scoped_students(user)

    school_id = params.get("school_id")
    if school_id:
        if not services.scoped_schools(user).filter(id=school_id).exists():
            raise ApiException("无权查看该学校数据", ErrorCode.FORBIDDEN, 403)
        students = students.filter(school_id=school_id)

    region_id = params.get("region_id")
    if region_id:
        if user.role not in (User.ROLE_PROVINCE, User.ROLE_CITY, User.ROLE_DISTRICT):
            raise ApiException("无权按地区查看数据", ErrorCode.FORBIDDEN, 403)
        # 越权保护：只能按自己可见的行政区过滤，防止区县号跨区/跨市查询
        if user.role != User.ROLE_PROVINCE:
            try:
                region_id_int = int(region_id)
            except (TypeError, ValueError):
                raise ApiException("region_id 非法", ErrorCode.INVALID_PARAM, 400)
            if region_id_int not in services.visible_region_ids(user):
                raise ApiException("无权查看该地区数据", ErrorCode.FORBIDDEN, 403)
        students = students.filter(school__region_id=region_id)

    grade = params.get("grade")
    if grade:
        # 兼容库里存代码 / 前端传中文两种情况
        students = students.filter(
            class_memberships__klass__grade__in=services.grade_variants(grade),
            class_memberships__status=services.APPROVED,
        ).distinct()

    return students


def _filtered_sheets(request, students):
    """按账号层级 + 查询参数收敛答卷范围。"""
    params = request.query_params
    sheets = (
        AnswerSheet.objects.filter(is_submitted=True, is_deleted=False, student__in=students)
        .select_related("paper", "student", "student__school", "student__school__region")
    )
    subject = params.get("subject")
    if subject:
        sheets = sheets.filter(paper__subject=subject)
    ptype = params.get("ptype")
    if ptype:
        sheets = sheets.filter(paper__ptype=ptype)
    return sheets


def _expected_by(students, field):
    """按分组字段统计应测学生数（同一学生只计一次）。"""
    rows = (
        students.order_by()
        .values(field)
        .annotate(total=Count("id", distinct=True))
        .values_list(field, "total")
    )
    return {label: total for label, total in rows if label}


def _expected_by_grade(students):
    """按归一化年级统计应测学生数（多班级学生只计一次）。"""
    buckets = {}
    rows = students.order_by().values_list("id", "class_memberships__klass__grade")
    for student_id, grade in rows:
        label = services.normalize_grade_label(grade)
        if not label:
            continue
        buckets.setdefault(label, set()).add(student_id)
    return {label: len(ids) for label, ids in buckets.items()}


def _summary(sheets, students):
    """汇总统计指标。"""
    rows = list(sheets.values("student_id", "total_score", "paper__subject", "paper__grade",
                              "paper__total_score", "student__school__name",
                              "student__school__region__name",
                              "student__school__region__parent__name"))
    participant_ids = {row["student_id"] for row in rows}
    total = len(rows)
    passed = 0
    rates = []
    for row in rows:
        full = float(row["paper__total_score"] or 0)
        score = float(row["total_score"] or 0)
        rate = score / full if full > 0 else 0
        rates.append(rate)
        if rate >= float(services.PASS_RATIO):
            passed += 1

    student_total = students.count()
    return {
        "student_total": student_total,
        "expected_count": student_total,
        "participant_count": len(participant_ids),
        "submission_count": total,
        "participation_rate": round(len(participant_ids) / student_total, 4) if student_total else 0,
        "average_score_rate": round(sum(rates) / len(rates), 4) if rates else 0,
        "pass_rate": round(passed / total, 4) if total else 0,
    }, rows


def _group(rows, key_func, label_func, expected_map=None):
    bucket = {}
    for row in rows:
        key = key_func(row)
        label = label_func(row)
        full = float(row["paper__total_score"] or 0)
        score = float(row["total_score"] or 0)
        item = bucket.setdefault(key, {
            "key": key,
            "label": label,
            "student_ids": set(),
            "submissions": 0,
            "rates": [],
            "pass": 0,
        })
        item["student_ids"].add(row["student_id"])
        item["submissions"] += 1
        rate = score / full if full > 0 else 0
        item["rates"].append(rate)
        if rate >= float(services.PASS_RATIO):
            item["pass"] += 1

    result = []
    for item in bucket.values():
        rates = item["rates"]
        expected = (expected_map or {}).get(item["label"]) or 0
        result.append({
            "key": item["key"],
            "label": item["label"],
            "participant_count": len(item["student_ids"]),
            "submission_count": item["submissions"],
            "expected_count": expected,
            "participation_rate": round(len(item["student_ids"]) / expected, 4) if expected else None,
            "average_score_rate": round(sum(rates) / len(rates), 4) if rates else 0,
            "pass_rate": round(item["pass"] / len(rates), 4) if rates else 0,
        })
    result.sort(key=lambda x: x["key"] or "")
    return result


def _subject_label(code):
    return dict([("music", "音乐"), ("art", "美术")]).get(code, code or "")


def _build_stats(request):
    # 先兜底提交已到期的未交答卷，避免学生超时未交导致漏统计、漏发证书
    services.auto_submit_overdue_sheets()

    students = _scoped_students(request)
    sheets = _filtered_sheets(request, students)

    summary, rows = _summary(sheets, students)
    student_total = summary["student_total"]
    by_subject = _group(
        rows,
        lambda r: r["paper__subject"],
        lambda r: _subject_label(r["paper__subject"]),
        expected_map={_subject_label(code): student_total for code in ("music", "art")},
    )
    by_grade = _group(
        rows,
        lambda r: services.normalize_grade_label(r["paper__grade"]) or "未填年级",
        lambda r: services.normalize_grade_label(r["paper__grade"]) or "未填年级",
        expected_map=_expected_by_grade(students),
    )
    by_school = _group(
        rows,
        lambda r: r["student__school__name"] or "",
        lambda r: r["student__school__name"] or "",
        expected_map=_expected_by(students, "school__name"),
    )
    by_region = _group(
        rows,
        lambda r: r["student__school__region__name"] or "未填地区",
        lambda r: r["student__school__region__name"] or "未填地区",
        expected_map=_expected_by(students, "school__region__name"),
    )
    by_city = _group(
        rows,
        lambda r: r["student__school__region__parent__name"] or "未填市州",
        lambda r: r["student__school__region__parent__name"] or "未填市州",
        expected_map=_expected_by(students, "school__region__parent__name"),
    )
    return {
        "summary": summary,
        "by_subject": by_subject,
        "by_grade": by_grade,
        "by_school": by_school,
        "by_region": by_region,
        "by_city": by_city,
    }


class StatsAssessmentView(APIView):
    """GET /api/exam/stats/assessment/ 测评数据统计。"""

    permission_classes = [STATS_ROLES]

    def get(self, request):
        return ApiResponse(data=_build_stats(request))


class StatsAssessmentExportView(APIView):
    """GET /api/exam/stats/assessment/export/ 统计导出 Excel。"""

    permission_classes = [STATS_ROLES]

    def get(self, request):
        stats = _build_stats(request)
        summary = stats["summary"]
        headers = ["统计项", "数值"]
        rows = [
            ["学生总数", summary["student_total"]],
            ["参与人数", summary["participant_count"]],
            ["提交份数", summary["submission_count"]],
            ["参与率", f"{summary['participation_rate'] * 100:.2f}%"],
            ["平均得分率", f"{summary['average_score_rate'] * 100:.2f}%"],
            ["及格率", f"{summary['pass_rate'] * 100:.2f}%"],
            ["", ""],
            ["分组", "参与人数", "提交份数", "平均得分率", "及格率"],
        ]
        for group_name, items in (
            ("学科", stats["by_subject"]),
            ("年级", stats["by_grade"]),
            ("学校", stats["by_school"]),
            ("地区", stats["by_region"]),
            ("市州", stats["by_city"]),
        ):
            for item in items:
                rows.append([
                    f"{group_name}-{item['label']}",
                    item["participant_count"],
                    item["submission_count"],
                    f"{item['average_score_rate'] * 100:.2f}%",
                    f"{item['pass_rate'] * 100:.2f}%",
                ])
        return xlsx_response("测评数据统计.xlsx", "测评统计", headers, rows)


class ParticipationExportView(APIView):
    """GET /api/exam/stats/participation/export/ 测评参与率导出（按学校）。"""

    permission_classes = [has_role(User.ROLE_PROVINCE)]

    def get(self, request):
        schools = services.scoped_schools(request.user).select_related("region", "region__parent")
        students = services.scoped_students(request.user)
        region_id = request.query_params.get("region_id")
        if region_id:
            schools = schools.filter(region_id=region_id)
            students = students.filter(school__region_id=region_id)

        participated = set(
            AnswerSheet.objects.filter(
                is_submitted=True, is_deleted=False, student__in=students
            ).values_list("student_id", flat=True)
        )
        counts = dict(
            students.values("school_id").annotate(total=Count("id")).values_list("school_id", "total")
        )
        participant_counts = dict(
            students.filter(id__in=participated)
            .values("school_id")
            .annotate(total=Count("id"))
            .values_list("school_id", "total")
        )

        rows = []
        for school in schools:
            total = counts.get(school.id, 0)
            joined = participant_counts.get(school.id, 0)
            rows.append([
                school.region.parent.name if school.region and school.region.parent else "",
                school.region.name if school.region else "",
                school.name,
                total,
                joined,
                f"{(joined / total * 100) if total else 0:.2f}%",
            ])

        headers = ["市州", "区县", "学校", "学生数", "参与人数", "参与率"]
        return xlsx_response("测评参与率.xlsx", "参与率", headers, rows)
