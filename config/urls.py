"""根路由装配。"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    # 认证
    path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # 业务模块
    path("api/users/", include("apps.users.urls")),
    path("api/org/", include("apps.org.urls")),
    path("api/classroom/", include("apps.classroom.urls")),
    path("api/questionbank/", include("apps.questionbank.urls")),
    path("api/exam/", include("apps.exam.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
