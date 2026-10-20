from rest_framework.routers import DefaultRouter

from apps.org import views

router = DefaultRouter()
router.register("regions", views.RegionViewSet, basename="region")
router.register("schools", views.SchoolViewSet, basename="school")

urlpatterns = router.urls
