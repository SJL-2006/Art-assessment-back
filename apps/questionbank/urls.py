from django.urls import path
from rest_framework.routers import DefaultRouter

from apps.questionbank import views

router = DefaultRouter()
router.register("courses", views.CourseViewSet, basename="course")
router.register("chapters", views.ChapterViewSet, basename="chapter")
router.register("questions", views.QuestionViewSet, basename="question")

urlpatterns = [
    # 试题资源删除：questions/{pk}/resources/{rid}/
    path(
        "questions/<int:pk>/resources/<int:rid>/",
        views.QuestionViewSet.as_view({"delete": "delete_resource"}),
        name="question-delete-resource",
    ),
]
urlpatterns += router.urls
