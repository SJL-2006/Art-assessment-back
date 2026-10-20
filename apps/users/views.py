from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.views import APIView

from apps.common.exceptions import ApiException
from apps.common.response import ApiResponse
from apps.users.serializers import ChangePasswordSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """注册。"""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class CurrentUserView(APIView):
    """当前登录用户信息。"""

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        return ApiResponse(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    """修改密码。"""

    @extend_schema(request=ChangePasswordSerializer, responses={200: None})
    def post(self, request):
        ser = ChangePasswordSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(ser.validated_data["old_password"]):
            raise ApiException("原密码不正确")
        user.set_password(ser.validated_data["new_password"])
        user.save()
        return ApiResponse(None, message="密码修改成功")
