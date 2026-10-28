from django.contrib import admin

from apps.content.models import FunClassKnowledge


@admin.register(FunClassKnowledge)
class FunClassKnowledgeAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "subject", "sort", "is_published")
    list_filter = ("subject", "is_published")
    search_fields = ("title",)
