from django.contrib import admin

from apps.classroom.models import ClassCourse, ClassRoom, ClassStudent, ClassTeacher


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "grade", "school", "head_teacher")
    search_fields = ("name", "code")
    list_filter = ("grade", "school")


@admin.register(ClassStudent)
class ClassStudentAdmin(admin.ModelAdmin):
    list_display = ("id", "klass", "student", "status")
    list_filter = ("status",)


@admin.register(ClassTeacher)
class ClassTeacherAdmin(admin.ModelAdmin):
    list_display = ("id", "klass", "teacher", "course", "status")
    list_filter = ("status",)


@admin.register(ClassCourse)
class ClassCourseAdmin(admin.ModelAdmin):
    list_display = ("id", "class_room", "course", "published_by", "created_at")
    search_fields = ("class_room__name", "course__name")
