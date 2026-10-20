from rest_framework.routers import DefaultRouter

from apps.exam import views

router = DefaultRouter()
router.register("papers", views.PaperViewSet, basename="paper")
router.register("paper-questions", views.PaperQuestionViewSet, basename="paper_question")
router.register("publishes", views.PaperPublishViewSet, basename="publish")
router.register("answer-sheets", views.AnswerSheetViewSet, basename="answer_sheet")
router.register("answers", views.AnswerViewSet, basename="answer")
router.register("certificates", views.CertificateViewSet, basename="certificate")

urlpatterns = router.urls
