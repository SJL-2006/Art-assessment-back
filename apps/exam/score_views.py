"""判分与评分接口（C 域 #6-#11、#21、教师答卷评分）。

接口清单：
6.  GET    /api/exam/students/{id}/extracurricular/     查看学生课外学习材料
7.  GET    /api/exam/students/{id}/scores/              查看学生测评成绩
8.  POST   /api/exam/students/{id}/scores/daily/        为学生平时表现评分
9.  GET    /api/exam/scores/template/                   成绩导入模板下载
10. POST   /api/exam/scores/import/                     导入学生线下成绩
11. POST   /api/exam/scores/supplement/                 测评成绩补录
21. GET    /api/exam/students/{id}/scores/export/       导出学生所有成绩
教师答卷评分（增量）：
    GET    /api/exam/teacher/answer-sheets/             教师看所带班级学生的答卷列表
    GET    /api/exam/teacher/answer-sheets/{id}/        教师看答卷详情（逐题 + 学生答案 + 自动判分）
    POST   /api/exam/teacher/answer-sheets/{id}/score/  教师对主观题打分（覆盖自动判分结果）
"""
from decimal import Decimal, InvalidOperation

from openpyxl import load_workbook
from rest_framework.views import APIView

from apps.classroom.models import ClassRoom, ClassStudent
from apps.common.exceptions import ApiException
from apps.common.permissions import has_role
from apps.common.response import ApiResponse, ErrorCode
from apps.exam import services
from apps.exam.exports import xlsx_response
from apps.exam.models import Answer, AnswerSheet, ExtracurricularUpload, PerformanceScore
from apps.questionbank.models import Course
from apps.users.models import User

# 复用 student_views 里已有的教师班级/学生范围函数
from apps.exam.student_views import _teacher_class_ids, _teacher_student_ids

SUBJECT_NAME_MAP = {
    "music": "音乐", "音乐": "music",
    "art": "美术", "美术": "art",
}


def _student_scores(student):
    """学生的测评成绩（已提交答卷）与平时表现评分。"""
    sheets = (
        AnswerSheet.objects.filter(student=student, is_submitted=True, is_deleted=False)
        .select_related("paper")
        .order_by("-submitted_at")
    )
    performances = (
        PerformanceScore.objects.filter(student=student, is_deleted=False)
        .select_related("course", "klass", "scorer")
        .order_by("-created_at")
    )
    return sheets, performances


def _student_score_rows(student):
    """导出用行数据。"""
    sheets, performances = _student_scores(student)
    rows = []
    for sheet in sheets:
        rows.append([
            "测评", sheet.paper.title, sheet.paper.get_subject_display(),
            float(sheet.total_score), float(sheet.paper.total_score),
            sheet.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if sheet.submitted_at else "",
            "",
        ])
    for item in performances:
        rows.append([
            "平时表现", "平时表现评分", item.course.name if item.course else "",
            float(item.score), 100,
            item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            item.comment,
        ])
    return rows


class StudentExtracurricularView(APIView):
    """GET /api/exam/students/{id}/extracurricular/ 查看学生课外学习材料。"""

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get(self, request, student_id):
        student = services.get_student_or_404(request.user, student_id)
        uploads = ExtracurricularUpload.objects.filter(student=student, is_deleted=False)
        data = [
            {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "image": request.build_absolute_uri(item.image.url) if item.image else "",
                "created_at": item.created_at,
            }
            for item in uploads
        ]
        return ApiResponse(data={"student_id": student.id, "list": data, "total": len(data)})


class StudentScoresView(APIView):
    """GET /api/exam/students/{id}/scores/ 查看学生测评成绩。"""

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get(self, request, student_id):
        student = services.get_student_or_404(request.user, student_id)
        sheets, performances = _student_scores(student)

        exam_list = [
            {
                "sheet_id": sheet.id,
                "paper_id": sheet.paper_id,
                "title": sheet.paper.title,
                "subject": sheet.paper.subject,
                "subject_display": sheet.paper.get_subject_display(),
                "ptype": sheet.paper.ptype,
                "score": float(sheet.total_score),
                "total_score": float(sheet.paper.total_score),
                "submitted_at": sheet.submitted_at,
            }
            for sheet in sheets
        ]
        performance_list = [
            {
                "id": item.id,
                "course": item.course.name if item.course else "",
                "klass": item.klass.name if item.klass else "",
                "score": float(item.score),
                "comment": item.comment,
                "scorer": item.scorer.real_name or item.scorer.username if item.scorer else "",
                "created_at": item.created_at,
            }
            for item in performances
        ]
        averages = {}
        for row in exam_list:
            averages.setdefault(row["subject_display"], []).append(row["score"])
        summary = {name: round(sum(vals) / len(vals), 2) for name, vals in averages.items() if vals}

        return ApiResponse(data={
            "student": {
                "id": student.id,
                "username": student.username,
                "real_name": student.real_name,
                "student_no": student.student_no,
            },
            "exams": exam_list,
            "performances": performance_list,
            "subject_average": summary,
        })


class StudentDailyScoreView(APIView):
    """POST /api/exam/students/{id}/scores/daily/ 为学生平时表现评分。"""

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def post(self, request, student_id):
        student = services.get_student_or_404(request.user, student_id)

        raw_score = request.data.get("score")
        if raw_score in (None, ""):
            raise ApiException("请填写评分", ErrorCode.INVALID_PARAM, 400)
        try:
            score = Decimal(str(raw_score))
        except (InvalidOperation, ValueError):
            raise ApiException("评分格式不正确", ErrorCode.INVALID_PARAM, 400)
        if score < 0 or score > 100:
            raise ApiException("评分需在 0-100 之间", ErrorCode.INVALID_PARAM, 400)

        course = None
        course_id = request.data.get("course_id")
        if course_id:
            course = Course.objects.filter(id=course_id).first()
            if course is None:
                raise ApiException("学科不存在", ErrorCode.NOT_FOUND, 404)

        klass = None
        klass_id = request.data.get("klass_id")
        if klass_id:
            klass = ClassRoom.objects.filter(id=klass_id).first()
            if klass is None:
                raise ApiException("班级不存在", ErrorCode.NOT_FOUND, 404)
        else:
            klass_id = (
                ClassStudent.objects.filter(student=student, status=services.APPROVED)
                .values_list("klass_id", flat=True)
                .first()
            )
            klass = ClassRoom.objects.filter(id=klass_id).first() if klass_id else None

        record = PerformanceScore.objects.create(
            student=student,
            klass=klass,
            course=course,
            scorer=request.user,
            score=score,
            comment=request.data.get("comment", ""),
        )
        return ApiResponse(
            data={
                "id": record.id,
                "student_id": student.id,
                "score": float(record.score),
                "course": course.name if course else "",
                "comment": record.comment,
            },
            message="评分成功",
        )


class ScoreTemplateView(APIView):
    """GET /api/exam/scores/template/ 成绩导入模板下载。"""

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get(self, request):
        headers = ["学籍号", "姓名", "班级编号", "学科", "分数", "评语"]
        rows = [
            ["20260101", "张三", "C2601", "音乐", 88, "课堂表现积极"],
            ["20260102", "李四", "C2601", "美术", 92, "作品完成度高"],
        ]
        return xlsx_response("成绩导入模板.xlsx", "成绩导入", headers, rows)


class ScoreImportView(APIView):
    """POST /api/exam/scores/import/ 导入学生线下成绩（xlsx）。"""

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            raise ApiException("请上传 Excel 文件（字段名 file）", ErrorCode.INVALID_PARAM, 400)
        try:
            workbook = load_workbook(upload, data_only=True)
        except Exception:
            raise ApiException("文件解析失败，请使用模板文件", ErrorCode.INVALID_PARAM, 400)

        sheet = workbook.active
        rows = list(sheet.iter_rows(min_row=2, values_only=True))
        allowed = services.scoped_students(request.user)

        success, errors = 0, []
        for index, row in enumerate(rows, start=2):
            if not row or all(value in (None, "") for value in row):
                continue
            values = list(row) + [None] * (6 - len(row))
            student_no, real_name, class_code, subject, score_value, comment = values[:6]

            student = None
            if student_no:
                student = allowed.filter(student_no=str(student_no).strip()).first()
            if student is None and real_name:
                # 姓名仅作兜底，且要求唯一匹配，避免重名时误入到他人名下
                name_matches = allowed.filter(real_name=str(real_name).strip())
                if name_matches.count() == 1:
                    student = name_matches.first()
            if student is None:
                errors.append({"row": index, "error": "学生不存在、不在管理范围内或姓名重复"})
                continue

            course = None
            if subject:
                code = SUBJECT_NAME_MAP.get(str(subject).strip())
                if code is None:
                    errors.append({"row": index, "error": "学科仅支持 音乐/美术"})
                    continue
                course = Course.objects.filter(code=code).first() or Course.objects.filter(
                    name="音乐" if code == "music" else "美术"
                ).first()

            try:
                score = Decimal(str(score_value))
            except (InvalidOperation, ValueError):
                errors.append({"row": index, "error": "分数格式不正确"})
                continue
            if score < 0 or score > 100:
                errors.append({"row": index, "error": "分数需在 0-100 之间"})
                continue

            klass = None
            if class_code:
                klass = ClassRoom.objects.filter(code=str(class_code).strip()).first()

            PerformanceScore.objects.create(
                student=student,
                klass=klass,
                course=course,
                scorer=request.user,
                score=score,
                comment=str(comment or ""),
            )
            success += 1

        return ApiResponse(
            data={"total": success + len(errors), "success": success, "failed": len(errors), "errors": errors},
            message="导入完成",
        )


class ScoreSupplementView(APIView):
    """POST /api/exam/scores/supplement/ 测评成绩补录（学校/区县/市州）。"""

    permission_classes = [has_role(User.ROLE_SCHOOL, User.ROLE_DISTRICT, User.ROLE_CITY)]

    def post(self, request):
        items = request.data.get("items")
        payloads = items if isinstance(items, list) else [request.data]
        if not payloads:
            raise ApiException("请提供补录数据", ErrorCode.INVALID_PARAM, 400)

        results, errors = [], []
        for index, item in enumerate(payloads):
            student_id = item.get("student_id")
            student_no = item.get("student_no")
            student = None
            if student_id:
                student = User.objects.filter(id=student_id, role=User.ROLE_STUDENT).first()
            elif student_no:
                student = User.objects.filter(student_no=student_no, role=User.ROLE_STUDENT).first()
            if student is None or not services.scoped_students(request.user).filter(id=student.id).exists():
                errors.append({"index": index, "error": "学生不存在或不在管理范围内"})
                continue

            try:
                score = Decimal(str(item.get("score")))
            except (InvalidOperation, ValueError, TypeError):
                errors.append({"index": index, "error": "分数格式不正确"})
                continue
            if score < 0 or score > 100:
                errors.append({"index": index, "error": "分数需在 0-100 之间"})
                continue

            course = Course.objects.filter(id=item.get("course_id")).first() if item.get("course_id") else None
            klass = ClassRoom.objects.filter(id=item.get("klass_id")).first() if item.get("klass_id") else None
            comment = str(item.get("comment") or "")
            record = PerformanceScore.objects.create(
                student=student,
                klass=klass,
                course=course,
                scorer=request.user,
                score=score,
                comment=f"测评补录：{comment}" if comment else "测评补录",
            )
            results.append({
                "id": record.id,
                "student_id": student.id,
                "student_no": student.student_no,
                "score": float(record.score),
            })

        return ApiResponse(
            data={"success": len(results), "failed": len(errors), "results": results, "errors": errors},
            message="补录完成",
        )


class StudentScoresExportView(APIView):
    """GET /api/exam/students/{id}/scores/export/ 导出学生所有成绩。"""

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get(self, request, student_id):
        student = services.get_student_or_404(request.user, student_id)
        headers = ["类型", "名称", "学科", "得分", "满分", "时间", "评语"]
        rows = _student_score_rows(student)
        filename = f"{student.real_name or student.username}_成绩.xlsx"
        return xlsx_response(filename, "学生成绩", headers, rows)


# --------------------------------------------------------------------------
# 教师视角的答卷评分接口
# --------------------------------------------------------------------------

class TeacherAnswerSheetListView(APIView):
    """GET /api/exam/teacher/answer-sheets/  教师看所带班级学生的答卷列表。

    查询参数：
    - klass_id: 按班级过滤
    - student_id: 按学生过滤
    - paper_id: 按试卷过滤
    - subject: 按学科过滤（music / art）
    - submitted_only: true=只看已提交（默认 true）
    """

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get(self, request):
        user = request.user
        if user.role == User.ROLE_TEACHER:
            student_ids = _teacher_student_ids(user)
            if not student_ids:
                return ApiResponse(data={"list": [], "total": 0})
        else:
            # 学校账号：全校（通过 services.scoped_students）
            student_ids = list(
                services.scoped_students(user).values_list("id", flat=True)
            )

        qs = AnswerSheet.objects.filter(
            student_id__in=student_ids, is_deleted=False,
        ).select_related("paper", "student", "publish").order_by("-submitted_at", "-created_at")

        klass_id = request.query_params.get("klass_id")
        student_id = request.query_params.get("student_id")
        paper_id = request.query_params.get("paper_id")
        subject = request.query_params.get("subject")
        submitted_only = request.query_params.get("submitted_only", "true").lower() == "true"

        if klass_id:
            qs = qs.filter(
                student__class_memberships__klass_id=klass_id,
                student__class_memberships__status=services.APPROVED,
                student__class_memberships__is_deleted=False,
            ).distinct()
        if student_id:
            qs = qs.filter(student_id=student_id)
        if paper_id:
            qs = qs.filter(paper_id=paper_id)
        if subject:
            qs = qs.filter(paper__subject=subject)
        if submitted_only:
            qs = qs.filter(is_submitted=True)

        rows = []
        for sheet in qs[:500]:  # 最多 500 条，避免一次拉太多
            rows.append({
                "sheet_id": sheet.id,
                "paper_id": sheet.paper_id,
                "paper_title": sheet.paper.title,
                "subject": sheet.paper.subject,
                "subject_display": sheet.paper.get_subject_display(),
                "ptype": sheet.paper.ptype,
                "student_id": sheet.student_id,
                "student_name": sheet.student.real_name or sheet.student.username,
                "student_no": sheet.student.student_no or "",
                "is_submitted": sheet.is_submitted,
                "total_score": float(sheet.total_score),
                "paper_total": float(sheet.paper.total_score or 0),
                "submitted_at": sheet.submitted_at,
                "publish_id": sheet.publish_id,
            })

        return ApiResponse(data={"list": rows, "total": qs.count()})


class TeacherAnswerSheetDetailView(APIView):
    """GET /api/exam/teacher/answer-sheets/{id}/  教师看答卷详情（逐题 + 学生答案 + 判分）。"""

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get(self, request, sheet_id):
        user = request.user
        sheet = AnswerSheet.objects.filter(pk=sheet_id, is_deleted=False).select_related(
            "paper", "student", "publish",
        ).first()
        if sheet is None:
            raise ApiException("答卷不存在", ErrorCode.NOT_FOUND, 404)

        # 权限检查：教师只能看自己所带班级学生的答卷
        if user.role == User.ROLE_TEACHER:
            allowed = _teacher_student_ids(user)
            if sheet.student_id not in allowed:
                raise ApiException("无权查看该学生答卷", ErrorCode.FORBIDDEN, 403)
        else:
            if not services.scoped_students(user).filter(id=sheet.student_id).exists():
                raise ApiException("无权查看该学生答卷", ErrorCode.FORBIDDEN, 403)

        # 逐题 + 学生答案
        answers_map = {a.question_id: a for a in sheet.answers.filter(is_deleted=False)}
        paper_questions = (
            sheet.paper.paper_questions.filter(is_deleted=False)
            .select_related("question")
            .order_by("sort", "id")
        )
        questions = []
        for pq in paper_questions:
            q = pq.question
            ans = answers_map.get(q.id)
            questions.append({
                "pq_id": pq.id,
                "question_id": q.id,
                "qtype": q.qtype,
                "qtype_display": q.get_qtype_display(),
                "stem": q.stem,
                "score": float(pq.score or q.score or 0),
                "sort": pq.sort,
                "options": q.options if q.qtype in ("single", "multiple") else [],
                "answer_text": ans.answer if ans else "",
                "is_correct": ans.is_correct if ans else None,
                "student_score": float(ans.score) if ans else 0,
                "teacher_scored": bool(ans and ans.is_correct is None and ans.score > 0),
                "analysis": q.analysis or "",
                "reference_answer": q.answer or "",
            })

        return ApiResponse(data={
            "sheet_id": sheet.id,
            "is_submitted": sheet.is_submitted,
            "total_score": float(sheet.total_score),
            "paper_total": float(sheet.paper.total_score or 0),
            "submitted_at": sheet.submitted_at,
            "started_at": sheet.started_at,
            "paper": {
                "id": sheet.paper.id,
                "title": sheet.paper.title,
                "subject": sheet.paper.subject,
                "subject_display": sheet.paper.get_subject_display(),
                "ptype": sheet.paper.ptype,
                "ptype_display": sheet.paper.get_ptype_display(),
            },
            "student": {
                "id": sheet.student.id,
                "name": sheet.student.real_name or sheet.student.username,
                "student_no": sheet.student.student_no or "",
            },
            "questions": questions,
            "question_count": len(questions),
        })


# ---------------------------------------------------------------------------
# 教师端课外材料审核（增量）
# ---------------------------------------------------------------------------

class TeacherExtracurricularListView(APIView):
    """GET /api/exam/teacher/extracurricular/  教师审核列表。

    Query 参数：
    - status: pending / approved / rejected  （空=全部）
    - klass_id: 班级过滤（空=全部所带班级）
    - subject: 学科过滤 music/art（空=全部）
    """

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get(self, request):
        from django.db.models import Count

        user = request.user
        qs = ExtracurricularUpload.objects.filter(is_deleted=False).select_related("student")

        # 权限范围：教师只能看自己所带班级学生的；学校管理员看全校
        if user.role == User.ROLE_TEACHER:
            student_ids = _teacher_student_ids(user)
            qs = qs.filter(student_id__in=student_ids)

        # 状态过滤
        status = request.GET.get("status", "").strip()
        if status in dict(ExtracurricularUpload.STATUS_CHOICES):
            qs = qs.filter(status=status)

        # 班级过滤（教师只传自己所带的班级 id）
        klass_id = request.GET.get("klass_id", "").strip()
        if klass_id.isdigit():
            from apps.classroom.models import ClassStudent
            qs = qs.filter(
                student_id__in=ClassStudent.objects.filter(
                    klass_id=int(klass_id), is_deleted=False
                ).values_list("student_id", flat=True)
            )

        qs = qs.order_by("-created_at")

        # 分页
        page = int(request.GET.get("page", 1) or 1)
        page_size = int(request.GET.get("page_size", 20) or 20)
        page_size = max(1, min(page_size, 100))
        total = qs.count()
        start = (page - 1) * page_size
        items = qs[start : start + page_size]

        def _row(item):
            st = item.status
            return {
                "id": item.id,
                "title": item.title,
                "description": item.description,
                "image": request.build_absolute_uri(item.image.url) if item.image else "",
                "status": st,
                "status_display": dict(ExtracurricularUpload.STATUS_CHOICES).get(st, st),
                "review_note": item.review_note,
                "reviewed_at": item.reviewed_at,
                "created_at": item.created_at,
                "student": {
                    "id": item.student.id,
                    "name": item.student.real_name or item.student.username,
                    "student_no": item.student.student_no or "",
                },
            }

        # 三种状态计数（前端 tab 用，在权限过滤后的 base_qs 基础上）
        base_qs = ExtracurricularUpload.objects.filter(is_deleted=False)
        if user.role == User.ROLE_TEACHER:
            base_qs = base_qs.filter(student_id__in=_teacher_student_ids(user))
        counts = {
            "pending":  base_qs.filter(status=ExtracurricularUpload.STATUS_PENDING).count(),
            "approved": base_qs.filter(status=ExtracurricularUpload.STATUS_APPROVED).count(),
            "rejected": base_qs.filter(status=ExtracurricularUpload.STATUS_REJECTED).count(),
        }

        return ApiResponse(data={
            "list": [_row(i) for i in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "counts": counts,
        })


class TeacherExtracurricularReviewView(APIView):
    """POST /api/exam/teacher/extracurricular/{id}/review/  审核通过或驳回。

    Body:
        { "action": "approve"|"reject", "note": "可选，审核备注" }
    """

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def post(self, request, pk):
        from django.utils import timezone

        try:
            upload = ExtracurricularUpload.objects.get(pk=pk, is_deleted=False)
        except ExtracurricularUpload.DoesNotExist:
            raise ApiException("资源不存在", status=404)

        user = request.user

        # 权限：教师只能审核自己所带班级学生的
        if user.role == User.ROLE_TEACHER:
            allowed = _teacher_student_ids(user)
            if upload.student_id not in allowed:
                raise ApiException("没有操作权限", status=403)

        action = request.data.get("action", "")
        note = (request.data.get("note") or "").strip()

        action_map = {
            "approve": ExtracurricularUpload.STATUS_APPROVED,
            "reject":  ExtracurricularUpload.STATUS_REJECTED,
        }
        if action not in action_map:
            raise ApiException("action 必须是 approve 或 reject", status=400)

        upload.status = action_map[action]
        upload.review_note = note
        upload.reviewed_at = timezone.now()
        upload.save(update_fields=["status", "review_note", "reviewed_at", "updated_at"])

        return ApiResponse(message="审核完成", data={
            "id": upload.id,
            "status": upload.status,
            "status_display": dict(ExtracurricularUpload.STATUS_CHOICES).get(upload.status),
            "reviewed_at": upload.reviewed_at,
        })


class TeacherAnswerSheetScoreView(APIView):
    """POST /api/exam/teacher/answer-sheets/{id}/score/  教师对答卷逐题打分（覆盖自动判分结果）。

    请求体：
        {
          "answers": [
            {"question_id": 101, "score": 8, "comment": "答得不错"},
            {"question_id": 102, "score": 0, "comment": "完全没答到点上"},
          ]
        }

    打分后自动重算 sheet.total_score。
    """

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def post(self, request, sheet_id):
        user = request.user
        sheet = AnswerSheet.objects.filter(pk=sheet_id, is_deleted=False).first()
        if sheet is None:
            raise ApiException("答卷不存在", ErrorCode.NOT_FOUND, 404)

        if user.role == User.ROLE_TEACHER:
            allowed = _teacher_student_ids(user)
            if sheet.student_id not in allowed:
                raise ApiException("无权为该答卷打分", ErrorCode.FORBIDDEN, 403)
        else:
            if not services.scoped_students(user).filter(id=sheet.student_id).exists():
                raise ApiException("无权为该答卷打分", ErrorCode.FORBIDDEN, 403)

        if not sheet.is_submitted:
            raise ApiException("答卷尚未提交，无法评分", ErrorCode.INVALID_PARAM, 400)

        answers = request.data.get("answers")
        if not isinstance(answers, list) or not answers:
            raise ApiException("answers 需为数组且非空", ErrorCode.INVALID_PARAM, 400)

        # 试卷上所有题目（用于校验 question_id + 取满分）
        paper_questions = {
            pq.question_id: pq for pq in sheet.paper.paper_questions.filter(is_deleted=False)
        }

        updated = 0
        for item in answers:
            qid = item.get("question_id")
            if qid is None or qid not in paper_questions:
                continue
            pq = paper_questions[qid]
            try:
                score = Decimal(str(item.get("score", 0)))
            except (InvalidOperation, ValueError, TypeError):
                continue
            max_score = Decimal(str(pq.score or 0))
            if score < 0:
                score = Decimal("0")
            if max_score > 0 and score > max_score:
                score = max_score

            ans, _created = Answer.objects.get_or_create(
                sheet=sheet, question_id=qid,
                defaults={"score": score},
            )
            ans.score = score
            # 教师手动打分 → is_correct 设为 None（表示人工判分）
            ans.is_correct = None
            ans.save(update_fields=["score", "is_correct", "updated_at"])
            updated += 1

        # 重算答卷总分（Python 层求和，避免引入 django.db.models.Sum）
        total = Decimal("0")
        for a in Answer.objects.filter(sheet=sheet, is_deleted=False):
            total += Decimal(str(a.score or 0))
        sheet.total_score = total
        sheet.save(update_fields=["total_score", "updated_at"])

        return ApiResponse(
            data={
                "sheet_id": sheet.id,
                "updated_count": updated,
                "total_score": float(sheet.total_score),
            },
            message=f"打分完成：更新 {updated} 题，总分 {float(sheet.total_score)}",
        )
