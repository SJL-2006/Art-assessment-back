"""证书接口（C 域 #22-#26）。

22. GET /api/exam/certificates/                            我的证书列表
23. GET /api/exam/certificates/{id}/                      证书详情
24. GET /api/exam/certificates/{id}/download/             下载证书
25. GET /api/exam/students/{id}/certificates/             查看学生证书（教师）
26. GET /api/exam/students/{id}/certificates/export/      导出学生证书
"""
from django.core.files.base import ContentFile
from django.http import FileResponse
from django.utils.html import escape
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView

from apps.common.exceptions import ApiException
from apps.common.pagination import StandardPagination
from apps.common.permissions import has_role
from apps.common.response import ApiResponse, ErrorCode
from apps.exam import services
from apps.exam.exports import xlsx_response
from apps.exam.models import Certificate
from apps.exam.serializers import CertificateSerializer
from apps.users.models import User


def _certificate_payload(cert, request):
    return {
        "id": cert.id,
        "title": cert.title,
        "subject": cert.subject,
        "subject_display": dict(cert._meta.get_field("subject").choices).get(cert.subject, cert.subject),
        "student_id": cert.student_id,
        "student_name": cert.student.real_name or cert.student.username,
        "sheet_id": cert.sheet_id,
        "score": float(cert.sheet.total_score) if cert.sheet else None,
        "file": request.build_absolute_uri(cert.file.url) if cert.file else "",
        "created_at": cert.created_at,
    }


def _certificate_html(cert):
    """无附件时按模板生成 HTML 证书。"""
    student_name = cert.student.real_name or cert.student.username
    score = f"{float(cert.sheet.total_score):g}" if cert.sheet else "-"
    subject = dict(cert._meta.get_field("subject").choices).get(cert.subject, cert.subject)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{escape(cert.title)}</title>
<style>
  body {{ margin: 0; font-family: "Songti SC", "SimSun", serif; background: #f5f5f0; }}
  .cert {{ width: 800px; margin: 40px auto; padding: 60px 70px; background: #fffdf8;
           border: 10px double #c9a227; text-align: center; }}
  h1 {{ font-size: 40px; letter-spacing: 8px; color: #8a6d1a; margin: 0 0 40px; }}
  .name {{ font-size: 30px; margin: 20px 0; }}
  .body {{ font-size: 18px; line-height: 2; color: #333; }}
  .footer {{ margin-top: 60px; font-size: 16px; color: #666; }}
</style>
</head>
<body>
  <div class="cert">
    <h1>艺术素质测评证书</h1>
    <div class="name">{escape(student_name)} 同学</div>
    <div class="body">
      在 {escape(subject)} 正式测评中表现优异，成绩 {escape(score)} 分，<br>
      特发此证，以资鼓励。
    </div>
    <div class="footer">
      证书编号：CERT-{cert.id:06d}<br>
      颁发日期：{cert.created_at.strftime("%Y-%m-%d")}
    </div>
  </div>
</body>
</html>"""


def _ensure_certificate_file(cert):
    """证书文件不存在时按模板生成并落盘。"""
    if cert.file and cert.file.name and cert.file.storage.exists(cert.file.name):
        return cert.file.path
    cert.file.save(f"certificate_{cert.id}.html", ContentFile(_certificate_html(cert).encode("utf-8")), save=True)
    return cert.file.path


class CertificateViewSet(viewsets.GenericViewSet):
    """学生端证书：列表 / 详情 / 下载。"""

    permission_classes = [has_role(User.ROLE_STUDENT)]
    pagination_class = StandardPagination
    serializer_class = CertificateSerializer

    def get_queryset(self):
        return (
            Certificate.objects.filter(student=self.request.user, is_deleted=False)
            .select_related("student", "sheet", "sheet__paper")
            .order_by("-created_at")
        )

    def list(self, request):
        """我的证书列表。"""
        items = [_certificate_payload(cert, request) for cert in self.get_queryset()]
        page = self.paginate_queryset(items)
        return self.get_paginated_response(page)

    def retrieve(self, request, pk=None):
        """证书详情。"""
        cert = self.get_queryset().filter(pk=pk).first()
        if cert is None:
            raise ApiException("证书不存在", ErrorCode.NOT_FOUND, 404)
        return ApiResponse(data=_certificate_payload(cert, request))

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """下载证书（无附件时自动生成 HTML 证书）。"""
        cert = self.get_queryset().filter(pk=pk).first()
        if cert is None:
            raise ApiException("证书不存在", ErrorCode.NOT_FOUND, 404)
        path = _ensure_certificate_file(cert)
        return FileResponse(
            open(path, "rb"),
            as_attachment=True,
            filename=f"certificate_{cert.id}.html",
            content_type="text/html; charset=utf-8",
        )


class StudentCertificateView(APIView):
    """GET /api/exam/students/{id}/certificates/ 查看学生证书（教师/学校）。"""

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get(self, request, student_id):
        student = services.get_student_or_404(request.user, student_id)
        certs = (
            Certificate.objects.filter(student=student, is_deleted=False)
            .select_related("student", "sheet")
            .order_by("-created_at")
        )
        return ApiResponse(data={
            "student_id": student.id,
            "list": [_certificate_payload(cert, request) for cert in certs],
            "total": certs.count(),
        })


class StudentCertificateExportView(APIView):
    """GET /api/exam/students/{id}/certificates/export/ 导出学生证书。"""

    permission_classes = [has_role(User.ROLE_TEACHER, User.ROLE_SCHOOL)]

    def get(self, request, student_id):
        student = services.get_student_or_404(request.user, student_id)
        certs = (
            Certificate.objects.filter(student=student, is_deleted=False)
            .select_related("sheet")
            .order_by("-created_at")
        )
        headers = ["证书编号", "证书名称", "学科", "关联测评", "成绩", "颁发时间"]
        rows = []
        for cert in certs:
            subject = dict(cert._meta.get_field("subject").choices).get(cert.subject, cert.subject)
            rows.append([
                f"CERT-{cert.id:06d}",
                cert.title,
                subject,
                cert.sheet.paper.title if cert.sheet else "",
                float(cert.sheet.total_score) if cert.sheet else "",
                cert.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            ])
        filename = f"{student.real_name or student.username}_证书.xlsx"
        return xlsx_response(filename, "学生证书", headers, rows)
