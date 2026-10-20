from django.contrib import admin

from apps.exam.models import Answer, AnswerSheet, Certificate, Paper, PaperPublish, PaperQuestion


@admin.register(Paper)
class PaperAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "subject", "ptype", "level", "grade", "status")
    list_filter = ("subject", "ptype", "level", "status")
    search_fields = ("title",)


@admin.register(PaperQuestion)
class PaperQuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "paper", "question", "sort", "score")


@admin.register(PaperPublish)
class PaperPublishAdmin(admin.ModelAdmin):
    list_display = ("id", "paper", "scope_type", "target_school", "target_class", "target_region", "status")
    list_filter = ("scope_type", "status")


@admin.register(AnswerSheet)
class AnswerSheetAdmin(admin.ModelAdmin):
    list_display = ("id", "paper", "student", "is_submitted", "total_score")
    list_filter = ("is_submitted",)


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ("id", "sheet", "question", "is_correct", "score")


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "student", "subject")
    list_filter = ("subject",)
