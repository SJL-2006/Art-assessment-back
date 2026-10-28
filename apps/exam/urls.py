"""exam 模块路由。

B 域：papers / paper-questions / publishes（views.py）
C 域：作答、判分评分、成绩、学生结果、统计、证书
     （answer_views / score_views / student_views / stats_views / certificate_views）
"""
from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.exam import (
    answer_views,
    certificate_views,
    score_views,
    stats_views,
    student_views,
    views,
)

router = DefaultRouter()
# ---- B 域 ----
router.register("papers", views.PaperViewSet, basename="paper")
router.register("paper-questions", views.PaperQuestionViewSet, basename="paper_question")
router.register("publishes", views.PaperPublishViewSet, basename="publish")
# ---- C 域 ----
router.register("answer-sheets", answer_views.AnswerSheetViewSet, basename="answer_sheet")
router.register("my-assessments", answer_views.MyAssessmentViewSet, basename="my_assessment")
router.register("my-scores", student_views.MyScoresViewSet, basename="my_score")
router.register("certificates", certificate_views.CertificateViewSet, basename="certificate")
router.register("extracurricular", student_views.ExtracurricularViewSet, basename="extracurricular")
# 保留答题记录的 AI 评分入口
router.register("answers", views.AnswerViewSet, basename="answer")

urlpatterns = [
    # 判分与评分
    path("scores/template/", score_views.ScoreTemplateView.as_view(), name="score_template"),
    path("scores/import/", score_views.ScoreImportView.as_view(), name="score_import"),
    path("scores/supplement/", score_views.ScoreSupplementView.as_view(), name="score_supplement"),
    # 教师/学校查看学生数据
    path(
        "students/<int:student_id>/extracurricular/",
        score_views.StudentExtracurricularView.as_view(),
        name="student_extracurricular",
    ),
    path("students/<int:student_id>/scores/", score_views.StudentScoresView.as_view(), name="student_scores"),
    path(
        "students/<int:student_id>/scores/daily/",
        score_views.StudentDailyScoreView.as_view(),
        name="student_daily_score",
    ),
    path(
        "students/<int:student_id>/scores/export/",
        score_views.StudentScoresExportView.as_view(),
        name="student_scores_export",
    ),
    path(
        "students/<int:student_id>/certificates/",
        certificate_views.StudentCertificateView.as_view(),
        name="student_certificates",
    ),
    path(
        "students/<int:student_id>/certificates/export/",
        certificate_views.StudentCertificateExportView.as_view(),
        name="student_certificates_export",
    ),
    # 学生成长曲线
    path("my-growth/", student_views.MyGrowthView.as_view(), name="my_growth"),
    # 学生查看班级测评信息
    path(
        "my-class/assessments/",
        student_views.MyClassAssessmentView.as_view(),
        name="my_class_assessments",
    ),
    # 数据统计
    path("stats/assessment/", stats_views.StatsAssessmentView.as_view(), name="stats_assessment"),
    path(
        "stats/assessment/export/",
        stats_views.StatsAssessmentExportView.as_view(),
        name="stats_assessment_export",
    ),
    path(
        "stats/participation/export/",
        stats_views.ParticipationExportView.as_view(),
        name="stats_participation_export",
    ),
] + router.urls
