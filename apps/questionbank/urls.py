from rest_framework.routers import DefaultRouter

from apps.questionbank import views

router = DefaultRouter()
router.register("courses", views.CourseViewSet, basename="course")
router.register("chapters", views.ChapterViewSet, basename="chapter")
router.register("questions", views.QuestionViewSet, basename="question")
router.register("question-resources", views.QuestionResourceViewSet, basename="question_resource")
router.register("question-reviews", views.QuestionReviewViewSet, basename="question_review")

urlpatterns = router.urls
