from rest_framework.routers import DefaultRouter

from apps.classroom import views

router = DefaultRouter()
router.register("classes", views.ClassRoomViewSet, basename="class")
router.register("class-students", views.ClassStudentViewSet, basename="class_student")
router.register("class-teachers", views.ClassTeacherViewSet, basename="class_teacher")

urlpatterns = router.urls
