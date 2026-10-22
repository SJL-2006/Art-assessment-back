
"""用户与认证相关视图。"""
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions
from rest_framework.views import APIView

from apps.common.exceptions import ApiException
from apps.common.response import ApiResponse
from apps.users.serializers import ChangePasswordSerializer, RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """#3 用户注册。

    公开接口，提交 username/password/role 等字段创建账号。
    """

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class CurrentUserView(APIView):
    """#4/#5 当前登录用户：GET 查询 / PUT 修改个人信息。"""

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        """获取当前用户信息。"""
        return ApiResponse(UserSerializer(request.user).data)

    def put(self, request):
        """修改当前用户的个人信息（real_name / phone / avatar / email 等）。"""
        ser = UserSerializer(request.user, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return ApiResponse(ser.data, message="个人信息修改成功")


class ChangePasswordView(APIView):
    """#6 修改密码。

    需传入 old_password + new_password，校验旧密码正确后更新。
    """

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
