"""根路由装配。"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.common.views_logs import LogViewSet
from apps.users.views_accounts import AccountViewSet

# ---------- 账号管理（role 参数化 User 资源） ----------
accounts_router = DefaultRouter()
accounts_router.register("", AccountViewSet, basename="account")

# ---------- 系统日志 ----------
logs_router = DefaultRouter()
logs_router.register("", LogViewSet, basename="log")

urlpatterns = [
    path("admin/", admin.site.urls),
    # 根路径欢迎页
    path("", lambda r: HttpResponse(
        "<h1>🎨 艺术测评系统后端</h1>"
        "<p>API 文档：<a href='/api/docs/'>Swagger UI</a></p>"
        "<p>API Schema：<a href='/api/schema/'>OpenAPI JSON</a></p>"
        "<p>Django Admin：<a href='/admin/'>/admin/</a></p>"
    )),
    # 认证
    path("api/auth/login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # OpenAPI / Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    # 业务模块
    path("api/users/", include("apps.users.urls")),
    path("api/accounts/", include(accounts_router.urls)),
    path("api/org/", include("apps.org.urls")),
    path("api/classroom/", include("apps.classroom.urls")),
    path("api/questionbank/", include("apps.questionbank.urls")),
    path("api/exam/", include("apps.exam.urls")),
    path("api/content/", include("apps.content.urls")),
    # 系统
    path("api/logs/", include(logs_router.urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
