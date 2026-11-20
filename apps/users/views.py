"""用户与认证相关视图。"""
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from PIL import Image
from rest_framework import generics, permissions
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.classroom.models import APPROVED, ClassRoom, ClassTeacher
from apps.common.exceptions import ApiException
from apps.common.response import ApiResponse, ErrorCode
from apps.users.models import User
from apps.users.serializers import ChangePasswordSerializer, RegisterSerializer, UserSerializer


class LoginSerializer(TokenObtainPairSerializer):
    """登录规则：学生用学籍号，教师用职工编号，管理员用姓名。"""

    def validate(self, attrs):
        username = (attrs.get(self.username_field) or "").strip()
        if username:
            if username.isdigit():
                user = (
                    User.objects.filter(student_no=username, is_active=True).first()
                    or User.objects.filter(staff_no=username, is_active=True).first()
                )
                if user:
                    attrs[self.username_field] = user.username
            else:
                named = User.objects.filter(username=username, is_active=True).first()
                if named:
                    if named.role == User.ROLE_STUDENT:
                        raise AuthenticationFailed("学生请使用学籍号登录")
                    if named.role == User.ROLE_TEACHER:
                        raise AuthenticationFailed("教师请使用职工编号登录")
        return super().validate(attrs)


class LoginView(TokenObtainPairView):
    """登录视图：学生用学籍号，教师用职工编号，管理员用姓名。"""
    serializer_class = LoginSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class SchoolCodeCheckView(APIView):
    """注册页学校编号校验：GET /api/users/school-check/?code=0001。"""

    permission_classes = [permissions.AllowAny]

    @extend_schema(responses={200: None})
    def get(self, request):
        from apps.org.models import School

        code = (request.query_params.get("code") or "").strip()
        school = School.objects.filter(code=code, is_deleted=False).first() if code else None
        if school is None:
            return ApiResponse({"exists": False})
        return ApiResponse({"exists": True, "code": school.code, "name": school.name})


class CurrentUserView(APIView):
    """当前登录用户：GET 查询 / PUT 修改个人信息。"""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request):
        data = UserSerializer(request.user, context={"request": request}).data
        if request.user.role == User.ROLE_TEACHER:
            data["head_class_count"] = ClassRoom.objects.filter(
                head_teacher=request.user, is_deleted=False,
            ).count()
            teach_qs = ClassTeacher.objects.filter(
                teacher=request.user, status=APPROVED, is_deleted=False,
            ).select_related("course")
            data["teaching_class_count"] = teach_qs.count()
            data["teaching_class_names"] = list(teach_qs.values_list("klass__name", flat=True))
            data["teaching_subjects"] = [
                code for code in teach_qs.values_list("course__code", flat=True) if code
            ]
        return ApiResponse(data)

    def put(self, request):
        ser = UserSerializer(
            request.user, data=request.data, partial=True, context={"request": request},
        )
        ser.is_valid(raise_exception=True)
        ser.save()
        return ApiResponse(ser.data, message="个人信息修改成功")


class MeAvatarView(APIView):
    """当前登录用户头像：POST 上传 / DELETE 重置。"""

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
    MAX_SIZE = 2 * 1024 * 1024  # 2MB

    @extend_schema(responses={200: None})
    def post(self, request):
        upload = request.FILES.get("avatar")
        if upload is None:
            raise ApiException("缺少头像文件", code=ErrorCode.INVALID_PARAM, status=400)
        if upload.content_type not in self.ALLOWED_TYPES:
            raise ApiException("仅支持 JPG / PNG / WEBP", code=ErrorCode.INVALID_PARAM, status=400)
        if upload.size > self.MAX_SIZE:
            raise ApiException("图片不能超过 2MB", code=ErrorCode.INVALID_PARAM, status=400)
        try:
            Image.open(upload).verify()
        except Exception:
            raise ApiException("文件不是有效图片", code=ErrorCode.INVALID_PARAM, status=400)
        upload.seek(0)

        user = request.user
        if user.avatar:
            user.avatar.delete(save=False)
        user.avatar = upload
        user.save(update_fields=["avatar"])
        return ApiResponse({"avatar": request.build_absolute_uri(user.avatar.url)})

    @extend_schema(responses={200: None})
    def delete(self, request):
        user = request.user
        if user.avatar:
            user.avatar.delete(save=False)
            user.avatar = ""
            user.save(update_fields=["avatar"])
        return ApiResponse({"avatar": None})


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]

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
