from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.questionbank import views

router = DefaultRouter()
router.register("courses", views.CourseViewSet, basename="course")
router.register("chapters", views.ChapterViewSet, basename="chapter")
router.register("questions", views.QuestionViewSet, basename="question")
router.register("resources", views.QuestionResourceViewSet, basename="resource")

urlpatterns = [
    # 题型字典（组卷/题库下拉使用）
    path("question-types/", views.QuestionTypeOptionsView.as_view(), name="question-types"),
    # 试题资源删除：questions/{pk}/resources/{rid}/
    path(
        "questions/<int:pk>/resources/<int:rid>/",
        views.QuestionViewSet.as_view({"delete": "delete_resource"}),
        name="question-delete-resource",
    ),
]
urlpatterns += router.urls
