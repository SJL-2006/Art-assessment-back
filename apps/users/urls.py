from django.urls import path

from apps.users import views

urlpatterns = [
    path("me/", views.CurrentUserView.as_view(), name="me"),
    path("me/avatar/", views.MeAvatarView.as_view(), name="me_avatar"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change_password"),
]
