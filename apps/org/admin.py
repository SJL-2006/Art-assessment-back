from django.contrib import admin

from apps.org.models import Region, School


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "level", "parent")
    list_filter = ("level",)
    search_fields = ("name", "code")


@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "region")
    search_fields = ("name", "code")
    list_filter = ("region",)
