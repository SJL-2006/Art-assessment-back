from django.contrib import admin

from apps.common.models import OperationLog


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "method", "path", "ip", "created_at")
    list_filter = ("method",)
    search_fields = ("path", "user__username")
    readonly_fields = ("user", "action", "module", "method", "path", "ip", "detail", "created_at")
