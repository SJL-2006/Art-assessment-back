from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.users.models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("扩展信息", {
            "fields": ("role", "real_name", "phone", "avatar", "student_no", "bio", "school", "region"),
        }),
    )
    list_display = ("username", "real_name", "role", "school", "phone", "is_active")
    list_filter = ("role", "is_active", "school")
    search_fields = ("username", "real_name", "phone", "student_no")
