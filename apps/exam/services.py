"""C 域（作答 / 判分 / 评分 / 统计 / 证书）公共服务。

统一收敛：
- 数据范围：按当前账号的行政层级过滤学生 / 学校；
- 判分：客观题自动判分、主观题留给教师或 AI 评分；
- 测评可作答判断：发布范围 + 时间窗口；
- 证书：正式测评达到及格线自动发放。
"""
import re
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone

from apps.classroom.models import ClassStudent
from apps.common.exceptions import ApiException
from apps.common.response import ErrorCode
from apps.exam.models import Answer, AnswerSheet, Certificate, Paper, PaperPublish
from apps.org.models import Region
from apps.users.models import User

# 已通过审核的班级关系状态
APPROVED = "approved"
# 可自动判分的客观题题型
OBJECTIVE_TYPES = {"single", "multiple", "judge", "fill"}
# 及格线（60%）
PASS_RATIO = Decimal("0.6")


# --------------------------------------------------------------------------
# 数据范围
# --------------------------------------------------------------------------
def visible_region_ids(user):
    """当前管理员可见的行政区 ID（自身 + 直接下级）。"""
    if not user.region_id:
        return []
    ids = [user.region_id]
    if user.role in (User.ROLE_PROVINCE, User.ROLE_CITY):
        ids += list(Region.objects.filter(parent_id=user.region_id).values_list("id", flat=True))
    return ids


def scoped_students(user):
    """按账号层级返回可见的学生 QuerySet。"""
    qs = User.objects.filter(role=User.ROLE_STUDENT, is_active=True)
    if user.is_superuser or user.role == User.ROLE_PROVINCE:
        return qs
    if user.role == User.ROLE_CITY:
        return qs.filter(school__region_id__in=visible_region_ids(user))
    if user.role == User.ROLE_DISTRICT:
        return qs.filter(school__region_id=user.region_id)
    if user.role in (User.ROLE_SCHOOL, User.ROLE_TEACHER):
        return qs.filter(school_id=user.school_id)
    return qs.none()


def scoped_schools(user):
    """按账号层级返回可见的学校 QuerySet。"""
    from apps.org.models import School

    qs = School.objects.all()
    if user.is_superuser or user.role == User.ROLE_PROVINCE:
        return qs
    if user.role == User.ROLE_CITY:
        return qs.filter(region_id__in=visible_region_ids(user))
    if user.role == User.ROLE_DISTRICT:
        return qs.filter(region_id=user.region_id)
    return qs.filter(id=user.school_id)


def get_student_or_404(user, student_id):
    """取学生并校验当前账号是否有权访问。"""
    student = User.objects.filter(id=student_id, role=User.ROLE_STUDENT).first()
    if student is None:
        raise ApiException("学生不存在", ErrorCode.NOT_FOUND, 404)
    if not user.is_superuser and not scoped_students(user).filter(id=student.id).exists():
        raise ApiException("无权访问该学生数据", ErrorCode.FORBIDDEN, 403)
    return student


# --------------------------------------------------------------------------
# 测评可作答范围
# --------------------------------------------------------------------------
def publish_is_open(publish, now=None):
    """发布时间窗口判断。"""
    now = now or timezone.now()
    if publish.start_at and publish.start_at > now:
        return False
    if publish.end_at and publish.end_at < now:
        return False
    return True


def student_class_ids(student):
    """学生已通过审核的班级 ID 列表。"""
    return list(
        ClassStudent.objects.filter(student=student, status=APPROVED).values_list("klass_id", flat=True)
    )


def student_grade(student):
    """取学生所在班级的年级。"""
    row = (
        ClassStudent.objects.filter(student=student, status=APPROVED)
        .exclude(klass__grade="")
        .values_list("klass__grade", flat=True)
        .first()
    )
    return row or ""


def student_region_chain(student):
    """学生学校所属行政区及其所有上级 ID。"""
    school = student.school
    if not school or not school.region_id:
        return []
    ids = []
    region = school.region
    while region is not None:
        ids.append(region.id)
        region = region.parent
    return ids


def available_publishes(student, now=None):
    """学生可作答的发布记录：状态已发布 + 在时间窗口内 + 命中发布范围。"""
    now = now or timezone.now()
    qs = (
        PaperPublish.objects.filter(status=PaperPublish.STATUS_PUBLISHED, paper__is_deleted=False)
        .select_related("paper", "target_class", "target_school", "target_region")
        .filter(Q(start_at__isnull=True) | Q(start_at__lte=now))
        .filter(Q(end_at__isnull=True) | Q(end_at__gte=now))
    )
    condition = Q(pk__in=[])
    class_ids = student_class_ids(student)
    if class_ids:
        condition |= Q(scope_type=PaperPublish.SCOPE_CLASS, target_class_id__in=class_ids)
    if student.school_id:
        condition |= Q(scope_type=PaperPublish.SCOPE_SCHOOL, target_school_id=student.school_id)
        grade = student_grade(student)
        if grade:
            condition |= Q(
                scope_type=PaperPublish.SCOPE_GRADE,
                target_school_id=student.school_id,
                paper__grade=grade,
            )
    region_ids = student_region_chain(student)
    if region_ids:
        condition |= Q(scope_type=PaperPublish.SCOPE_REGION, target_region_id__in=region_ids)
    return qs.filter(condition)


def get_available_publish(student, publish_id):
    """取一条学生可作答的发布记录，不可作答时抛业务异常。"""
    publish = available_publishes(student).filter(id=publish_id).first()
    if publish is None:
        raise ApiException("测评不存在或不在作答范围内", ErrorCode.NOT_FOUND, 404)
    return publish


def sheet_of(student, publish):
    return AnswerSheet.objects.filter(
        student=student, paper=publish.paper, publish=publish
    ).first()


# --------------------------------------------------------------------------
# 自动判分
# --------------------------------------------------------------------------
def _normalize(text):
    return re.sub(r"\s+", "", str(text or "")).strip().lower()


def _tokens(text):
    parts = re.split(r"[\s,，;；、/|]+", str(text or "").strip().upper())
    return {p for p in parts if p}


_JUDGE_TRUE = {"对", "正确", "是", "true", "t", "√", "1", "a"}
_JUDGE_FALSE = {"错", "错误", "否", "false", "f", "×", "x", "0", "b"}


def grade_one(qtype, correct_answer, given_answer, full_score):
    """单题判分。

    返回 (is_correct, score)：
    - 客观题：答对得满分，答错/未答得 0 分；
    - 主观题：is_correct 返回 None，分数 0（由教师评分或 AI 评分补分）。
    """
    full = Decimal(str(full_score or 0))
    if qtype not in OBJECTIVE_TYPES:
        return None, Decimal("0")
    if not str(given_answer or "").strip():
        return False, Decimal("0")

    if qtype == "multiple":
        ok = _tokens(correct_answer) == _tokens(given_answer)
    elif qtype == "judge":
        correct = _normalize(correct_answer)
        given = _normalize(given_answer)
        if correct in _JUDGE_TRUE:
            correct = "true"
        elif correct in _JUDGE_FALSE:
            correct = "false"
        if given in _JUDGE_TRUE:
            given = "true"
        elif given in _JUDGE_FALSE:
            given = "false"
        ok = correct == given
    elif qtype == "fill":
        ok = _normalize(correct_answer) == _normalize(given_answer) or (
            _tokens(correct_answer) == _tokens(given_answer)
        )
    else:
        ok = _normalize(correct_answer) == _normalize(given_answer)
    return ok, (full if ok else Decimal("0"))


def submit_sheet(sheet):
    """提交答卷并触发自动判分（幂等）。"""
    if sheet.is_submitted:
        return sheet

    paper = sheet.paper
    links = list(paper.paper_questions.select_related("question"))
    existing = {a.question_id: a for a in sheet.answers.all()}
    total = Decimal("0")

    for link in links:
        question = link.question
        answer = existing.get(question.id)
        given = answer.answer if answer else ""
        is_correct, score = grade_one(question.qtype, question.answer, given, link.score)
        total += score
        if answer is None:
            answer = Answer(sheet=sheet, question=question)
        answer.is_correct = is_correct
        answer.score = score
        answer.save()

    # 试卷未配置题目时，按试卷总分兜底
    sheet.total_score = total
    sheet.is_submitted = True
    sheet.submitted_at = timezone.now()
    sheet.save(update_fields=["total_score", "is_submitted", "submitted_at", "updated_at"])
    issue_certificate(sheet)
    return sheet


def ensure_sheet_editable(sheet):
    """校验答卷可继续作答；超时则自动提交并提示。"""
    if sheet.is_submitted:
        raise ApiException("答卷已提交，不能修改", ErrorCode.CONFLICT, 409)
    publish = sheet.publish
    if publish and publish.end_at and publish.end_at < timezone.now():
        submit_sheet(sheet)
        raise ApiException("测评已结束，答卷已自动提交", ErrorCode.CONFLICT, 409)


def auto_submit_overdue_sheets(now=None):
    """把已到结束时间仍未提交的答卷全部自动提交（幂等），返回提交份数。

    用于「测评限时自动提交」：既可由定时任务调用，也可在统计接口前兜底调用，
    避免学生超时未交导致漏统计、漏发证书。
    """
    now = now or timezone.now()
    overdue = (
        AnswerSheet.objects.filter(
            is_submitted=False,
            is_deleted=False,
            publish__end_at__isnull=False,
            publish__end_at__lt=now,
        )
        .select_related("publish", "paper")
    )
    submitted = 0
    for sheet in overdue:
        submit_sheet(sheet)
        submitted += 1
    return submitted


# --------------------------------------------------------------------------
# 证书
# --------------------------------------------------------------------------
def issue_certificate(sheet):
    """正式测评达到及格线时自动发放证书。"""
    paper = sheet.paper
    if paper.ptype != Paper.TYPE_FORMAL:
        return None
    try:
        total = Decimal(str(paper.total_score or 0))
        if total <= 0:
            return None
        ratio = Decimal(str(sheet.total_score or 0)) / total
    except (InvalidOperation, ZeroDivisionError):
        return None
    if ratio < PASS_RATIO:
        return None
    title = f"{paper.get_subject_display()}正式测评证书"
    certificate, _ = Certificate.objects.get_or_create(
        student=sheet.student,
        sheet=sheet,
        subject=paper.subject,
        defaults={"title": title},
    )
    return certificate


# --------------------------------------------------------------------------
# 序列化辅助
# --------------------------------------------------------------------------
def resource_payload(resource, request):
    url = ""
    if resource.file:
        try:
            url = request.build_absolute_uri(resource.file.url)
        except ValueError:
            url = ""
    return {"id": resource.id, "rtype": resource.rtype, "url": url}


def question_payload(link, request, show_answer=False):
    """题目输出；未提交时不返回答案与解析。"""
    question = link.question
    data = {
        "id": question.id,
        "sort": link.sort,
        "qtype": question.qtype,
        "qtype_display": question.get_qtype_display(),
        "difficulty": question.difficulty,
        "grade": question.grade,
        "stem": question.stem,
        "options": question.options or [],
        "score": str(link.score),
        "resources": [resource_payload(r, request) for r in question.resources.all()],
    }
    if show_answer:
        data["answer"] = question.answer
        data["analysis"] = question.analysis
    return data


def sheet_payload(sheet):
    return {
        "id": sheet.id,
        "paper_id": sheet.paper_id,
        "publish_id": sheet.publish_id,
        "started_at": sheet.started_at,
        "submitted_at": sheet.submitted_at,
        "is_submitted": sheet.is_submitted,
        "total_score": str(sheet.total_score),
    }
