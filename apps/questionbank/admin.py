from django.contrib import admin

from apps.questionbank.models import Chapter, Course, Question, QuestionResource, QuestionReview


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code")
    search_fields = ("name", "code")


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "course", "parent", "sort")
    list_filter = ("course",)


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "stem", "course", "qtype", "difficulty", "grade", "status")
    list_filter = ("course", "qtype", "difficulty", "status")
    search_fields = ("stem",)


@admin.register(QuestionResource)
class QuestionResourceAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "rtype", "file")


@admin.register(QuestionReview)
class QuestionReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "question", "reviewer", "result", "comment")
    list_filter = ("result",)
