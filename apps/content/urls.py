from rest_framework.routers import DefaultRouter

from apps.content.views import FunClassKnowledgeViewSet

router = DefaultRouter()
router.register("knowledge", FunClassKnowledgeViewSet, basename="fun_knowledge")

urlpatterns = router.urls
