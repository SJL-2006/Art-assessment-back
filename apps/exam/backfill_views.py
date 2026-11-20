"""测评补录台账接口（B01-B12）。

统一前缀：/api/exam/backfills/
状态机：pending（待教师核实）→ verified（待学校入账）→ approved（已入账）
        pending / verified 可被驳回；pending 可被学生撤回。
"""
import csv
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.views import APIView

from apps.classroom.models import APPROVED, ClassStudent
from apps.common.exceptions import ApiException
from apps.common.response import ApiResponse
from apps.exam import services
from apps.exam.models import AnswerSheet, BackfillEvent, BackfillRequest, PerformanceScore
from apps.exam.student_views import _teacher_class_ids, _teacher_student_ids
from apps.questionbank.models import Course
from apps.users.models import User

SUBJECT_LABELS = {"music": "音乐", "art": "美术"}
STATUS_LABELS = dict(BackfillRequest.STATUS_CHOICES)
SOURCE_LABELS = {
    BackfillRequest.SOURCE_STUDENT: "学生申请",
    BackfillRequest.SOURCE_TEACHER: "教师补录",
    BackfillRequest.SOURCE_SCHOOL: "学校补录",
    BackfillRequest.SOURCE_DISTRICT: "区县补录",
    BackfillRequest.SOURCE_CITY: "市州补录",
    BackfillRequest.SOURCE_PROVINCE: "省级补录",
}
DIRECT_ACTION_LABELS = {
    BackfillRequest.SOURCE_TEACHER: "教师直接补录",
    BackfillRequest.SOURCE_SCHOOL: "学校直接补录",
    BackfillRequest.SOURCE_DISTRICT: "区县直接补录",
    BackfillRequest.SOURCE_CITY: "市州直接补录",
    BackfillRequest.SOURCE_PROVINCE: "省级直接补录",
}
REASONS = ["缺考未参加", "设备故障未提交", "生病请假", "跨校转学补测", "其他原因"]

READ_ROLES = {
    User.ROLE_STUDENT, User.ROLE_TEACHER, User.ROLE_SCHOOL,
    User.ROLE_DISTRICT, User.ROLE_CITY, User.ROLE_PROVINCE,
}
ADMIN_ROLES = {User.ROLE_SCHOOL, User.ROLE_DISTRICT, User.ROLE_CITY, User.ROLE_PROVINCE}


# --------------------------------------------------------------------------
# 公共辅助
# --------------------------------------------------------------------------
def _name(user):
    if user is None:
        return ""
    return user.real_name or user.username


def _fmt(dt):
    if dt is None:
        return ""
    if timezone.is_aware(dt):
        dt = timezone.localtime(dt)
    return dt.strftime("%Y-%m-%d %H:%M")


def _ensure_role(user, roles):
    if user.is_superuser:
        return
    if user.role not in roles:
        raise ApiException("当前角色无权执行该操作", "forbidden_role", 403)


def _parse_score(value):
    if value in (None, ""):
        raise ApiException("请填写成绩", "score_required", 422)
    try:
        score = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ApiException("成绩格式不正确", "invalid_params", 400)
    if score < 0 or score > 100:
        raise ApiException("成绩需在 0-100 之间", "score_out_of_range", 422)
    return score.quantize(Decimal("0.1"))


def _parse_date(value):
    parsed = parse_date(str(value or "").strip())
    if parsed is None:
        raise ApiException("测评日期格式应为 YYYY-MM-DD", "invalid_params", 400)
    return parsed


def _required_text(data, key, message, max_length=None):
    value = str(data.get(key) or "").strip()
    if not value:
        raise ApiException(message, "invalid_params", 400)
    if max_length and len(value) > max_length:
        raise ApiException(f"{message}，最长 {max_length} 个字符", "invalid_params", 400)
    return value


def _validate_subject(value):
    subject = str(value or "").strip()
    if subject not in SUBJECT_LABELS:
        raise ApiException("学科仅支持 music / art", "invalid_params", 400)
    return subject


def _course_for_subject(subject):
    course = Course.objects.filter(code=subject).first()
    if course is None:
        course = Course.objects.filter(name=SUBJECT_LABELS.get(subject, "")).first()
    return course


def _write_score(record, scorer):
    """复用现有成绩写入：新增一条平时表现评分记录。"""
    return PerformanceScore.objects.create(
        student=record.student,
        klass=record.klass,
        course=_course_for_subject(record.subject),
        scorer=scorer,
        score=record.score,
        comment=f"测评补录：{record.paper_name}"[:255],
    )


def _add_event(record, action, actor, note=""):
    return BackfillEvent.objects.create(
        backfill=record,
        action=action,
        actor=actor,
        actor_role=getattr(actor, "role", "") or "",
        note=(note or "")[:255],
    )


def _next_code():
    prefix = f"BF-{timezone.localdate().strftime('%Y%m%d')}-"
    seq = BackfillRequest.objects.filter(code__startswith=prefix).count() + 1
    while BackfillRequest.objects.filter(code=f"{prefix}{seq:03d}").exists():
        seq += 1
    return f"{prefix}{seq:03d}"


def _serialize(record, with_timeline=False):
    data = {
        "id": record.id,
        "code": record.code,
        "status": record.status,
        "status_label": STATUS_LABELS.get(record.status, record.status),
        "source_role": record.source_role,
        "source_label": SOURCE_LABELS.get(record.source_role, record.source_role),
        "student": {
            "id": record.student_id,
            "name": _name(record.student),
            "student_no": record.student_no or (record.student.student_no or ""),
        },
        "school": (
            {"id": record.school_id, "name": record.school.name} if record.school_id else None
        ),
        "klass": (
            {"id": record.klass_id, "name": record.klass.name} if record.klass_id else None
        ),
        "subject": record.subject,
        "subject_label": SUBJECT_LABELS.get(record.subject, record.subject),
        "paper_name": record.paper_name,
        "exam_date": record.exam_date.strftime("%Y-%m-%d") if record.exam_date else "",
        "score": float(record.score) if record.score is not None else None,
        "reason": record.reason,
        "detail": record.detail,
        "reject_reason": record.reject_reason,
        "score_record_id": record.score_record_id,
        "created_at": _fmt(record.created_at),
        "updated_at": _fmt(record.updated_at),
    }
    if with_timeline:
        data["timeline"] = [
            {
                "action": event.action,
                "actor": _name(event.actor),
                "actor_role": event.actor_role,
                "note": event.note,
                "at": _fmt(event.created_at),
            }
            for event in record.events.select_related("actor").order_by("created_at", "id")
        ]
    return data


def _scoped_qs(user):
    """按角色自动收敛补录记录范围。"""
    qs = BackfillRequest.objects.filter(is_deleted=False).select_related(
        "student", "school", "klass",
    )
    if user.is_superuser or user.role == User.ROLE_PROVINCE:
        return qs
    if user.role == User.ROLE_STUDENT:
        return qs.filter(student=user)
    if user.role == User.ROLE_TEACHER:
        class_ids = _teacher_class_ids(user)
        student_ids = _teacher_student_ids(user)
        if not class_ids and not student_ids:
            return qs.none()
        return qs.filter(Q(klass_id__in=class_ids) | Q(student_id__in=student_ids)).distinct()
    if user.role == User.ROLE_SCHOOL:
        return qs.filter(school_id=user.school_id)
    if user.role == User.ROLE_DISTRICT:
        return qs.filter(school__region_id=user.region_id)
    if user.role == User.ROLE_CITY:
        return qs.filter(school__region_id__in=services.visible_region_ids(user))
    return qs.none()


def _load_record(user, pk):
    record = BackfillRequest.objects.filter(pk=pk, is_deleted=False).select_related(
        "student", "school", "klass",
    ).first()
    if record is None:
        raise ApiException("补录记录不存在", "not_found", 404)
    if not _scoped_qs(user).filter(pk=pk).exists():
        raise ApiException("记录不在当前账号数据范围内", "forbidden_scope", 403)
    return record


def _teacher_can_handle(user, record):
    if user.is_superuser:
        return True
    if user.role != User.ROLE_TEACHER:
        return False
    if record.klass_id and record.klass_id in _teacher_class_ids(user):
        return True
    return record.student_id in set(_teacher_student_ids(user))


def _school_can_handle(user, record):
    if user.is_superuser:
        return True
    return (
        user.role == User.ROLE_SCHOOL
        and user.school_id is not None
        and record.school_id == user.school_id
    )


def _resolve_klass(student, klass_id=None):
    qs = ClassStudent.objects.filter(
        student=student, status=APPROVED, is_deleted=False,
    ).select_related("klass")
    if klass_id:
        row = qs.filter(klass_id=klass_id).first()
        if row is None:
            raise ApiException("班级不存在或学生不在该班级", "invalid_params", 400)
        return row.klass
    row = qs.first()
    return row.klass if row else None


def _scope_info(user):
    if user.is_superuser:
        return {"role": "superuser", "name": "全部"}
    name = ""
    if user.role in (User.ROLE_STUDENT, User.ROLE_TEACHER):
        name = _name(user)
    elif user.role == User.ROLE_SCHOOL:
        name = user.school.name if user.school_id else ""
    elif user.role in (User.ROLE_DISTRICT, User.ROLE_CITY):
        name = user.region.name if user.region_id else ""
    elif user.role == User.ROLE_PROVINCE:
        name = "省级"
    return {"role": user.role, "name": name}


def _apply_filters(qs, request):
    params = request.query_params

    status = str(params.get("status") or "").strip()
    if status:
        statuses = [item.strip() for item in status.split(",") if item.strip()]
        if statuses:
            qs = qs.filter(status__in=statuses)

    subject = str(params.get("subject") or "").strip()
    if subject:
        qs = qs.filter(subject=subject)

    school = str(params.get("school") or "").strip()
    if school.isdigit():
        qs = qs.filter(school_id=int(school))

    klass = str(params.get("klass") or "").strip()
    if klass.isdigit():
        qs = qs.filter(klass_id=int(klass))

    student = str(params.get("student") or "").strip()
    if student.isdigit():
        qs = qs.filter(student_id=int(student))

    keyword = str(params.get("keyword") or "").strip()
    if keyword:
        qs = qs.filter(
            Q(student__real_name__icontains=keyword)
            | Q(student__student_no__icontains=keyword)
            | Q(student__username__icontains=keyword)
            | Q(student_no__icontains=keyword)
            | Q(paper_name__icontains=keyword)
            | Q(code__icontains=keyword)
        )

    date_from = parse_date(str(params.get("date_from") or "").strip())
    if date_from:
        qs = qs.filter(created_at__date__gte=date_from)
    date_to = parse_date(str(params.get("date_to") or "").strip())
    if date_to:
        qs = qs.filter(created_at__date__lte=date_to)

    ordering = str(params.get("ordering") or "-created_at").strip()
    if ordering.lstrip("-") not in ("created_at", "exam_date"):
        ordering = "-created_at"
    return qs.order_by(ordering, "-id")


# --------------------------------------------------------------------------
# B01 / B04  列表与提交申请
# --------------------------------------------------------------------------
class BackfillListCreateView(APIView):
    """GET /api/exam/backfills/ 列表；POST /api/exam/backfills/ 学生提交申请。"""

    def get(self, request):
        user = request.user
        _ensure_role(user, READ_ROLES)
        qs = _apply_filters(_scoped_qs(user), request)
        total = qs.count()

        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            page = 1
        try:
            page_size = int(request.query_params.get("page_size", 20))
        except (TypeError, ValueError):
            page_size = 20
        page_size = min(max(page_size, 1), 100)

        start = (page - 1) * page_size
        rows = [_serialize(item) for item in qs[start:start + page_size]]
        return ApiResponse(data={"list": rows, "total": total, "page": page, "page_size": page_size})

    def post(self, request):
        user = request.user
        _ensure_role(user, {User.ROLE_STUDENT})

        data = request.data
        subject = _validate_subject(data.get("subject"))
        paper_name = _required_text(data, "paper_name", "请填写测评名称", 128)
        exam_date = _parse_date(data.get("exam_date"))
        reason = _required_text(data, "reason", "请填写补录原因", 64)
        detail = str(data.get("detail") or "").strip()
        klass_id = data.get("klass_id")
        klass = _resolve_klass(user, int(klass_id) if str(klass_id or "").isdigit() else None)

        duplicate = BackfillRequest.objects.filter(
            student=user,
            paper_name=paper_name,
            exam_date=exam_date,
            is_deleted=False,
        ).exclude(
            status__in=[BackfillRequest.STATUS_REJECTED, BackfillRequest.STATUS_CANCELLED],
        ).exists()
        if duplicate:
            raise ApiException("该测评的补录申请已存在", "duplicate_application", 409)

        with transaction.atomic():
            record = BackfillRequest.objects.create(
                code=_next_code(),
                status=BackfillRequest.STATUS_PENDING,
                source_role=BackfillRequest.SOURCE_STUDENT,
                student=user,
                student_no=(user.student_no or "")[:32],
                school=user.school,
                klass=klass,
                subject=subject,
                paper_name=paper_name,
                exam_date=exam_date,
                reason=reason,
                detail=detail,
                created_by=user,
            )
            _add_event(record, "提交补录申请", user, detail)

        record = BackfillRequest.objects.select_related("student", "school", "klass").get(pk=record.pk)
        return ApiResponse(data=_serialize(record), message="提交成功", status=201)


# --------------------------------------------------------------------------
# B02 / B12  统计与可选项
# --------------------------------------------------------------------------
class BackfillStatsView(APIView):
    """GET /api/exam/backfills/stats/ 流转计数与 KPI。"""

    def get(self, request):
        user = request.user
        _ensure_role(user, READ_ROLES)
        qs = _scoped_qs(user)

        counts = {row["status"]: row["c"] for row in qs.values("status").annotate(c=Count("id"))}
        data = {
            "scope": _scope_info(user),
            "total": sum(counts.values()),
            "pending": counts.get(BackfillRequest.STATUS_PENDING, 0),
            "verified": counts.get(BackfillRequest.STATUS_VERIFIED, 0),
            "approved": counts.get(BackfillRequest.STATUS_APPROVED, 0),
            "rejected": counts.get(BackfillRequest.STATUS_REJECTED, 0),
            "cancelled": counts.get(BackfillRequest.STATUS_CANCELLED, 0),
            "students": qs.values("student_id").distinct().count(),
            "schools": qs.exclude(school__isnull=True).values("school_id").distinct().count(),
        }
        return ApiResponse(data=data)


class BackfillOptionsView(APIView):
    """GET /api/exam/backfills/options/ 补录原因与最近测评名称。"""

    def get(self, request):
        user = request.user
        _ensure_role(user, READ_ROLES)

        sheets = AnswerSheet.objects.filter(is_submitted=True, is_deleted=False)
        if user.role == User.ROLE_STUDENT:
            sheets = sheets.filter(student=user)
        elif user.role == User.ROLE_TEACHER:
            student_ids = _teacher_student_ids(user)
            if not student_ids:
                return ApiResponse(data={"reasons": REASONS, "recent_titles": []})
            sheets = sheets.filter(student_id__in=student_ids)
        elif not (user.is_superuser or user.role == User.ROLE_PROVINCE):
            student_ids = list(
                services.scoped_students(user).values_list("id", flat=True)[:5000]
            )
            if not student_ids:
                return ApiResponse(data={"reasons": REASONS, "recent_titles": []})
            sheets = sheets.filter(student_id__in=student_ids)

        titles = []
        for title in sheets.order_by("-submitted_at", "-id").values_list("paper__title", flat=True)[:200]:
            if title and title not in titles:
                titles.append(title)
            if len(titles) >= 10:
                break
        return ApiResponse(data={"reasons": REASONS, "recent_titles": titles})


# --------------------------------------------------------------------------
# B03  详情
# --------------------------------------------------------------------------
class BackfillDetailView(APIView):
    """GET /api/exam/backfills/{id}/ 补录详情（含 timeline）。"""

    def get(self, request, pk):
        _ensure_role(request.user, READ_ROLES)
        record = _load_record(request.user, pk)
        return ApiResponse(data=_serialize(record, with_timeline=True))


# --------------------------------------------------------------------------
# B05  教师核实并录入成绩
# --------------------------------------------------------------------------
class BackfillVerifyView(APIView):
    """POST /api/exam/backfills/{id}/verify/"""

    def post(self, request, pk):
        user = request.user
        _ensure_role(user, {User.ROLE_TEACHER})
        record = _load_record(user, pk)
        if not _teacher_can_handle(user, record):
            raise ApiException("该记录所属班级不在您的教学范围内", "forbidden_scope", 403)

        score = _parse_score(request.data.get("score"))
        note = str(request.data.get("note") or "").strip()

        with transaction.atomic():
            record = BackfillRequest.objects.select_for_update().get(pk=record.pk)
            if record.status != BackfillRequest.STATUS_PENDING:
                raise ApiException("当前状态不允许该操作", "invalid_status", 409)
            record.score = score
            record.status = BackfillRequest.STATUS_VERIFIED
            record.verified_by = user
            record.verified_at = timezone.now()
            record.save(update_fields=[
                "score", "status", "verified_by", "verified_at", "updated_at",
            ])
            event_note = f"成绩 {score} 分" + (f"；{note}" if note else "")
            _add_event(record, "教师核实并录入成绩", user, event_note)

        record = BackfillRequest.objects.select_related("student", "school", "klass").get(pk=record.pk)
        return ApiResponse(data=_serialize(record), message="核实成功")


# --------------------------------------------------------------------------
# B06  入账前修改成绩
# --------------------------------------------------------------------------
class BackfillScoreView(APIView):
    """PATCH /api/exam/backfills/{id}/score/"""

    def patch(self, request, pk):
        user = request.user
        _ensure_role(user, {User.ROLE_TEACHER, User.ROLE_SCHOOL})
        record = _load_record(user, pk)

        if user.role == User.ROLE_TEACHER:
            if not _teacher_can_handle(user, record):
                raise ApiException("该记录所属班级不在您的教学范围内", "forbidden_scope", 403)
            action = "教师修改成绩"
        else:
            if not _school_can_handle(user, record):
                raise ApiException("该记录不属于本校", "forbidden_scope", 403)
            action = "学校修改成绩"

        score = _parse_score(request.data.get("score"))
        note = str(request.data.get("note") or "").strip()

        with transaction.atomic():
            record = BackfillRequest.objects.select_for_update().get(pk=record.pk)
            if record.status != BackfillRequest.STATUS_VERIFIED:
                raise ApiException("当前状态不允许该操作", "invalid_status", 409)
            record.score = score
            record.save(update_fields=["score", "updated_at"])
            event_note = f"成绩调整为 {score} 分" + (f"；{note}" if note else "")
            _add_event(record, action, user, event_note)

        record = BackfillRequest.objects.select_related("student", "school", "klass").get(pk=record.pk)
        return ApiResponse(data=_serialize(record), message="修改成功")


# --------------------------------------------------------------------------
# B07  学校确认入账
# --------------------------------------------------------------------------
class BackfillApproveView(APIView):
    """POST /api/exam/backfills/{id}/approve/"""

    def post(self, request, pk):
        user = request.user
        _ensure_role(user, {User.ROLE_SCHOOL})
        record = _load_record(user, pk)
        if not _school_can_handle(user, record):
            raise ApiException("该记录不属于本校", "forbidden_scope", 403)

        note = str(request.data.get("note") or "").strip()

        try:
            with transaction.atomic():
                record = BackfillRequest.objects.select_for_update().select_related(
                    "student", "school", "klass",
                ).get(pk=record.pk)
                if record.status == BackfillRequest.STATUS_APPROVED:
                    raise ApiException("该记录已入账，请勿重复操作", "already_approved", 409)
                if record.status != BackfillRequest.STATUS_VERIFIED:
                    raise ApiException("当前状态不允许该操作", "invalid_status", 409)
                if record.score is None:
                    raise ApiException("请先录入成绩", "score_required", 422)

                score_record = _write_score(record, user)
                record.score_record_id = score_record.id
                record.status = BackfillRequest.STATUS_APPROVED
                record.approved_by = user
                record.approved_at = timezone.now()
                record.save(update_fields=[
                    "score_record_id", "status", "approved_by", "approved_at", "updated_at",
                ])
                _add_event(record, "确认入账", user, note or f"成绩 {record.score} 分已入账")
        except ApiException:
            raise
        except Exception:
            raise ApiException("成绩写入失败，事务已回滚", "score_write_failed", 502)

        record = BackfillRequest.objects.select_related("student", "school", "klass").get(pk=record.pk)
        return ApiResponse(data=_serialize(record), message="入账成功")


# --------------------------------------------------------------------------
# B08  驳回
# --------------------------------------------------------------------------
class BackfillRejectView(APIView):
    """POST /api/exam/backfills/{id}/reject/"""

    def post(self, request, pk):
        user = request.user
        _ensure_role(user, {User.ROLE_TEACHER, User.ROLE_SCHOOL})
        record = _load_record(user, pk)

        if user.role == User.ROLE_TEACHER:
            if not _teacher_can_handle(user, record):
                raise ApiException("该记录所属班级不在您的教学范围内", "forbidden_scope", 403)
            allowed = {BackfillRequest.STATUS_PENDING}
        else:
            if not _school_can_handle(user, record):
                raise ApiException("该记录不属于本校", "forbidden_scope", 403)
            allowed = {BackfillRequest.STATUS_PENDING, BackfillRequest.STATUS_VERIFIED}

        reason = _required_text(request.data, "reason", "请填写驳回原因", 255)

        with transaction.atomic():
            record = BackfillRequest.objects.select_for_update().get(pk=record.pk)
            if record.status not in allowed:
                raise ApiException("当前状态不允许该操作", "invalid_status", 409)
            record.status = BackfillRequest.STATUS_REJECTED
            record.reject_reason = reason
            record.rejected_by = user
            record.rejected_at = timezone.now()
            record.save(update_fields=[
                "status", "reject_reason", "rejected_by", "rejected_at", "updated_at",
            ])
            _add_event(record, "驳回补录申请", user, reason)

        record = BackfillRequest.objects.select_related("student", "school", "klass").get(pk=record.pk)
        return ApiResponse(data=_serialize(record), message="已驳回")


# --------------------------------------------------------------------------
# B09  学生撤回
# --------------------------------------------------------------------------
class BackfillWithdrawView(APIView):
    """POST /api/exam/backfills/{id}/withdraw/"""

    def post(self, request, pk):
        user = request.user
        _ensure_role(user, {User.ROLE_STUDENT})
        record = _load_record(user, pk)
        if record.student_id != user.id:
            raise ApiException("只能撤回本人申请", "forbidden_scope", 403)

        with transaction.atomic():
            record = BackfillRequest.objects.select_for_update().get(pk=record.pk)
            if record.status != BackfillRequest.STATUS_PENDING:
                raise ApiException("当前状态不允许该操作", "invalid_status", 409)
            record.status = BackfillRequest.STATUS_CANCELLED
            record.save(update_fields=["status", "updated_at"])
            _add_event(record, "学生撤回申请", user, "学生撤回补录申请")

        record = BackfillRequest.objects.select_related("student", "school", "klass").get(pk=record.pk)
        return ApiResponse(data=_serialize(record), message="已撤回")


# --------------------------------------------------------------------------
# B10  教师 / 管理端直接补录
# --------------------------------------------------------------------------
class BackfillDirectView(APIView):
    """POST /api/exam/backfills/direct/"""

    def post(self, request):
        user = request.user
        _ensure_role(user, {User.ROLE_TEACHER} | ADMIN_ROLES)

        data = request.data
        student_id = str(data.get("student_id") or "").strip()
        if not student_id.isdigit():
            raise ApiException("请选择学生", "invalid_params", 400)
        student = User.objects.filter(id=int(student_id), role=User.ROLE_STUDENT).first()
        if student is None:
            raise ApiException("学生不存在", "not_found", 404)

        if user.role == User.ROLE_TEACHER:
            if student.id not in set(_teacher_student_ids(user)):
                raise ApiException("该学生不在您的教学范围内", "forbidden_scope", 403)
        elif not (user.is_superuser or user.role == User.ROLE_PROVINCE):
            if not services.scoped_students(user).filter(id=student.id).exists():
                raise ApiException("该学生不在您的数据范围内", "forbidden_scope", 403)

        subject = _validate_subject(data.get("subject"))
        paper_name = _required_text(data, "paper_name", "请填写测评名称", 128)
        exam_date = _parse_date(data.get("exam_date"))
        reason = _required_text(data, "reason", "请填写补录原因", 64)
        detail = str(data.get("detail") or "").strip()
        score = _parse_score(data.get("score"))

        klass_id = data.get("klass_id")
        klass = _resolve_klass(student, int(klass_id) if str(klass_id or "").isdigit() else None)

        source_role = user.role if user.role in DIRECT_ACTION_LABELS else BackfillRequest.SOURCE_PROVINCE
        action = DIRECT_ACTION_LABELS.get(source_role, "直接补录")
        immediate = user.role in ADMIN_ROLES or user.is_superuser
        event_note = f"成绩 {score} 分" + (f"；{detail}" if detail else "")

        try:
            with transaction.atomic():
                record = BackfillRequest.objects.create(
                    code=_next_code(),
                    status=BackfillRequest.STATUS_APPROVED if immediate else BackfillRequest.STATUS_VERIFIED,
                    source_role=source_role,
                    student=student,
                    student_no=(student.student_no or "")[:32],
                    school=student.school or (user.school if user.role == User.ROLE_SCHOOL else None),
                    klass=klass,
                    subject=subject,
                    paper_name=paper_name,
                    exam_date=exam_date,
                    score=score,
                    reason=reason,
                    detail=detail,
                    created_by=user,
                    verified_by=user,
                    verified_at=timezone.now(),
                )
                if immediate:
                    score_record = _write_score(record, user)
                    record.score_record_id = score_record.id
                    record.status = BackfillRequest.STATUS_APPROVED
                    record.approved_by = user
                    record.approved_at = timezone.now()
                    record.save(update_fields=[
                        "score_record_id", "status", "approved_by", "approved_at", "updated_at",
                    ])
                _add_event(record, action, user, event_note)
        except ApiException:
            raise
        except Exception:
            raise ApiException("成绩写入失败，事务已回滚", "score_write_failed", 502)

        record = BackfillRequest.objects.select_related("student", "school", "klass").get(pk=record.pk)
        return ApiResponse(data=_serialize(record), message="补录成功")


# --------------------------------------------------------------------------
# B11  CSV 导出
# --------------------------------------------------------------------------
class BackfillExportView(APIView):
    """GET /api/exam/backfills/export/"""

    def get(self, request):
        user = request.user
        _ensure_role(user, {User.ROLE_TEACHER} | ADMIN_ROLES)
        qs = _apply_filters(_scoped_qs(user), request).select_related(
            "student", "school", "klass", "created_by",
        )

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response.write("\ufeff")
        response["Content-Disposition"] = (
            f'attachment; filename="backfills_{timezone.localdate().strftime("%Y%m%d")}.csv"'
        )
        writer = csv.writer(response)
        writer.writerow([
            "申请编号", "学生", "学籍号", "学校", "班级", "学科", "测评名称",
            "补录成绩", "测评日期", "补录原因", "来源", "提交人", "提交时间", "状态",
        ])
        for record in qs.iterator():
            writer.writerow([
                record.code,
                _name(record.student),
                record.student_no or (record.student.student_no or ""),
                record.school.name if record.school_id else "",
                record.klass.name if record.klass_id else "",
                SUBJECT_LABELS.get(record.subject, record.subject),
                record.paper_name,
                f"{record.score}" if record.score is not None else "",
                record.exam_date.strftime("%Y-%m-%d") if record.exam_date else "",
                record.reason,
                SOURCE_LABELS.get(record.source_role, record.source_role),
                _name(record.created_by),
                _fmt(record.created_at),
                STATUS_LABELS.get(record.status, record.status),
            ])
        return response
