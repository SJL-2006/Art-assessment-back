"""测评作答接口（C 域 #1-#5，另含学生端报告与记录）。

接口清单：
1. GET    /api/exam/my-assessments/                      我可作答的测评列表
2. GET    /api/exam/my-assessments/{id}/                 试卷详情（含题目与资源）
3. POST   /api/exam/answer-sheets/                       开始作答
4. PUT    /api/exam/answer-sheets/{id}/answers/          保存答题进度
5. POST   /api/exam/answer-sheets/{id}/submit/           提交答卷（自动判分）
   GET    /api/exam/my-assessments/records/               测评记录
   GET    /api/exam/my-assessments/{id}/report/           统计分析报告
"""
from decimal import Decimal

from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import viewsets
from rest_framework.decorators import action

from apps.common.exceptions import ApiException
from apps.common.pagination import StandardPagination
from apps.common.permissions import has_role
from apps.common.response import ApiResponse, ErrorCode
from apps.common.views import BaseViewSet
from apps.exam import services
from apps.exam.models import Answer, AnswerSheet, PaperPublish
from apps.exam.serializers import AnswerSheetSerializer
from apps.users.models import User


class MyAssessmentViewSet(viewsets.GenericViewSet):
    """学生端：可作答测评列表 / 试卷详情 / 测评记录 / 统计报告。"""

    permission_classes = [has_role(User.ROLE_STUDENT)]
    pagination_class = StandardPagination

    def _item(self, publish, sheet=None):
        paper = publish.paper
        return {
            "id": publish.id,
            "paper_id": paper.id,
            "title": paper.title,
            "subject": paper.subject,
            "subject_display": paper.get_subject_display(),
            "ptype": paper.ptype,
            "ptype_display": paper.get_ptype_display(),
            "grade": paper.grade,
            "duration": paper.duration,
            "total_score": str(paper.total_score),
            "question_count": paper.paper_questions.count(),
            "start_at": publish.start_at,
            "end_at": publish.end_at,
            "sheet_id": sheet.id if sheet else None,
            "is_submitted": bool(sheet and sheet.is_submitted),
            "my_score": str(sheet.total_score) if sheet and sheet.is_submitted else None,
        }

    def list(self, request):
        """我可作答的测评列表（按发布范围与时间过滤）。"""
        publishes = list(services.available_publishes(request.user).order_by("-created_at"))
        sheets = {
            s.publish_id: s
            for s in AnswerSheet.objects.filter(student=request.user, publish_id__in=[p.id for p in publishes])
        }
        items = [self._item(p, sheets.get(p.id)) for p in publishes]
        page = self.paginate_queryset(items)
        return self.get_paginated_response(page)

    def retrieve(self, request, pk=None):
        """试卷详情：题目 + 音频/图片资源；已提交才返回答案与解析。"""
        publish = services.get_available_publish(request.user, pk)
        paper = publish.paper
        sheet = services.sheet_of(request.user, publish)
        submitted = bool(sheet and sheet.is_submitted)

        links = paper.paper_questions.select_related("question").prefetch_related("question__resources")
        questions = [services.question_payload(link, request, show_answer=submitted) for link in links]

        saved = []
        if sheet is not None:
            saved = [
                {"question_id": a.question_id, "answer": a.answer, "score": str(a.score),
                 "is_correct": a.is_correct}
                for a in sheet.answers.all()
            ]

        data = {
            "id": publish.id,
            "paper": {
                "id": paper.id,
                "title": paper.title,
                "subject": paper.subject,
                "subject_display": paper.get_subject_display(),
                "ptype": paper.ptype,
                "ptype_display": paper.get_ptype_display(),
                "grade": paper.grade,
                "duration": paper.duration,
                "total_score": str(paper.total_score),
                "question_count": len(questions),
            },
            "start_at": publish.start_at,
            "end_at": publish.end_at,
            "is_open": services.publish_is_open(publish),
            "questions": questions,
            "sheet": services.sheet_payload(sheet) if sheet else None,
            "my_answers": saved,
        }
        return ApiResponse(data=data)

    @action(detail=False, methods=["get"], url_path="records")
    def records(self, request):
        """测评记录列表（已提交答卷）。"""
        sheets = (
            AnswerSheet.objects.filter(student=request.user)
            .select_related("paper", "publish")
            .order_by("-created_at")
        )
        items = [
            {
                "sheet_id": s.id,
                "publish_id": s.publish_id,
                "paper_id": s.paper_id,
                "title": s.paper.title,
                "subject": s.paper.subject,
                "subject_display": s.paper.get_subject_display(),
                "ptype": s.paper.ptype,
                "ptype_display": s.paper.get_ptype_display(),
                "total_score": str(s.paper.total_score),
                "my_score": str(s.total_score),
                "is_submitted": s.is_submitted,
                "started_at": s.started_at,
                "submitted_at": s.submitted_at,
            }
            for s in sheets
        ]
        page = self.paginate_queryset(items)
        return self.get_paginated_response(page)

    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        """测评统计分析报告：得分、正确率、逐题明细、班级平均分。"""
        publish = services.get_available_publish(request.user, pk)
        sheet = services.sheet_of(request.user, publish)
        if sheet is None:
            raise ApiException("尚未开始作答", ErrorCode.NOT_FOUND, 404)
        # 超时未提交：服务端自动提交后再出报告
        if not sheet.is_submitted and publish.end_at and publish.end_at < timezone.now():
            services.submit_sheet(sheet)
        if not sheet.is_submitted:
            raise ApiException("答卷尚未提交", ErrorCode.INVALID_PARAM, 400)

        paper = sheet.paper
        links = list(paper.paper_questions.select_related("question"))
        answers = {a.question_id: a for a in sheet.answers.all()}

        details = []
        correct = wrong = subjective = 0
        for link in links:
            question = link.question
            answer = answers.get(question.id)
            item = {
                "question_id": question.id,
                "sort": link.sort,
                "qtype": question.qtype,
                "qtype_display": question.get_qtype_display(),
                "stem": question.stem,
                "my_answer": answer.answer if answer else "",
                "correct_answer": question.answer,
                "analysis": question.analysis,
                "full_score": str(link.score),
                "score": str(answer.score if answer else 0),
                "is_correct": answer.is_correct if answer else None,
            }
            if answer and answer.is_correct is True:
                correct += 1
            elif answer and answer.is_correct is False:
                wrong += 1
            else:
                subjective += 1
            details.append(item)

        class_qs = AnswerSheet.objects.filter(
            is_submitted=True, is_deleted=False, paper=paper
        )
        class_average = class_qs.aggregate(value=Avg("total_score"))["value"] or 0

        total_full = paper.total_score or 0
        my_score = sheet.total_score or 0
        ratio = float(my_score) / float(total_full) if float(total_full) > 0 else 0
        data = {
            "sheet_id": sheet.id,
            "publish_id": publish.id,
            "paper_title": paper.title,
            "subject": paper.subject,
            "subject_display": paper.get_subject_display(),
            "ptype": paper.ptype,
            "total_score": str(total_full),
            "my_score": str(my_score),
            "correct_rate": round(correct / len(links), 4) if links else 0,
            "score_rate": round(ratio, 4),
            "correct_count": correct,
            "wrong_count": wrong,
            "subjective_count": subjective,
            "question_count": len(links),
            "class_average": str(round(Decimal(str(class_average)), 2)),
            "class_size": class_qs.count(),
            "submitted_at": sheet.submitted_at,
            "details": details,
        }
        return ApiResponse(data=data)


class AnswerSheetViewSet(BaseViewSet):
    """答卷：开始作答 / 保存进度 / 提交判分。"""

    queryset = AnswerSheet.objects.all()
    serializer_class = AnswerSheetSerializer
    permission_classes = [has_role(User.ROLE_STUDENT)]

    def _my_sheet(self, request, pk):
        sheet = (
            AnswerSheet.objects.filter(pk=pk, student=request.user)
            .select_related("paper", "publish")
            .first()
        )
        if sheet is None:
            raise ApiException("答卷不存在", ErrorCode.NOT_FOUND, 404)
        return sheet

    def create(self, request):
        """开始作答：body {publish_id} 或 {paper_id}，重复调用返回同一份答卷。"""
        publish_id = request.data.get("publish_id")
        paper_id = request.data.get("paper_id")

        if publish_id:
            publish = services.get_available_publish(request.user, publish_id)
        elif paper_id:
            publish = services.available_publishes(request.user).filter(paper_id=paper_id).first()
            if publish is None:
                raise ApiException("试卷不存在或不在作答范围内", ErrorCode.NOT_FOUND, 404)
        else:
            raise ApiException("请提供 publish_id 或 paper_id", ErrorCode.INVALID_PARAM, 400)

        if not services.publish_is_open(publish):
            raise ApiException("测评尚未开始或已结束", ErrorCode.CONFLICT, 409)

        sheet, created = AnswerSheet.objects.get_or_create(
            paper=publish.paper,
            student=request.user,
            publish=publish,
            defaults={"started_at": timezone.now()},
        )
        if sheet.is_submitted:
            raise ApiException("该测评已提交，不能重新作答", ErrorCode.CONFLICT, 409)
        if sheet.started_at is None:
            sheet.started_at = timezone.now()
            sheet.save(update_fields=["started_at", "updated_at"])

        return ApiResponse(data=services.sheet_payload(sheet), message="开始作答")

    @action(detail=True, methods=["put"], url_path="answers")
    def save_answers(self, request, pk=None):
        """保存答题进度：body {"answers": [{"question_id": 1, "answer": "A"}]}。"""
        sheet = self._my_sheet(request, pk)
        services.ensure_sheet_editable(sheet)

        payload = request.data.get("answers", request.data)
        if not isinstance(payload, list):
            raise ApiException("answers 需为数组", ErrorCode.INVALID_PARAM, 400)

        valid_ids = set(sheet.paper.paper_questions.values_list("question_id", flat=True))
        saved = 0
        for row in payload:
            if not isinstance(row, dict):
                continue
            question_id = row.get("question_id")
            if question_id not in valid_ids:
                raise ApiException(f"试题 {question_id} 不属于本试卷", ErrorCode.INVALID_PARAM, 400)
            answer, _ = Answer.objects.update_or_create(
                sheet=sheet,
                question_id=question_id,
                defaults={"answer": str(row.get("answer", ""))},
            )
            saved += 1

        return ApiResponse(
            data={"sheet_id": sheet.id, "saved": saved, "is_submitted": sheet.is_submitted},
            message="保存成功",
        )

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """提交答卷并触发客观题自动判分。"""
        sheet = self._my_sheet(request, pk)
        services.ensure_sheet_editable(sheet)
        services.submit_sheet(sheet)

        answers = sheet.answers.all()
        correct = answers.filter(is_correct=True).count()
        wrong = answers.filter(is_correct=False).count()
        pending = answers.filter(is_correct__isnull=True).count()
        data = services.sheet_payload(sheet)
        data.update({
            "paper_total_score": str(sheet.paper.total_score),
            "correct_count": correct,
            "wrong_count": wrong,
            "subjective_pending": pending,
            "pass": float(sheet.total_score) >= float(sheet.paper.total_score or 0) * 0.6,
        })
        return ApiResponse(data=data, message="提交成功")
