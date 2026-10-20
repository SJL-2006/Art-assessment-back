"""User 相关序列化器。"""
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    """用户通用序列化器。"""
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "username", "real_name", "phone", "avatar", "role", "role_display",
            "student_no", "school", "region", "email", "date_joined",
        ]
        read_only_fields = ["id", "username", "role", "date_joined"]


class RegisterSerializer(serializers.ModelSerializer):
    """用户注册。"""
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["username", "password", "role", "real_name", "phone", "student_no", "school", "region"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class ChangePasswordSerializer(serializers.Serializer):
    """修改密码。"""
    old_password = serializers.CharField()
    new_password = serializers.CharField(validators=[validate_password])


# ============ 账号管理（role 参数化） ============

class AccountManageSerializer(serializers.ModelSerializer):
    """#28-32 后台账号管理：role 由调用方指定，字段随 role 而异。"""

    class Meta:
        model = User
        fields = [
            "id", "username", "password", "real_name", "phone", "avatar",
            "role", "student_no", "school", "region", "email", "is_active", "date_joined",
        ]
        read_only_fields = ["id", "date_joined"]
        extra_kwargs = {"password": {"write_only": True, "required": False}}

    def validate_role(self, value):
        # 学校管理员不能创建/删除省/市/区县管理员
        request = self.context.get("request")
        if request and request.user.role == User.ROLE_SCHOOL:
            if value in (User.ROLE_PROVINCE, User.ROLE_CITY, User.ROLE_DISTRICT):
                raise serializers.ValidationError("学校管理员不能创建该角色账号")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class BatchCreateAccountSerializer(serializers.Serializer):
    """#34 批量创建账号（教师等）。"""
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    prefix = serializers.CharField(max_length=32, help_text="用户名前缀")
    count = serializers.IntegerField(min_value=1, max_value=500)
    default_password = serializers.CharField(required=False, default="123456", allow_blank=True)
    real_names = serializers.ListField(child=serializers.CharField(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.org.models import Region, School

        self.fields["school"] = serializers.PrimaryKeyRelatedField(
            queryset=School.objects.all(), required=False, allow_null=True,
        )
        self.fields["region"] = serializers.PrimaryKeyRelatedField(
            queryset=Region.objects.all(), required=False, allow_null=True,
        )


class BatchImportAccountSerializer(serializers.Serializer):
    """#35 批量导入账号（学生/外校教师，接 Excel/CSV 解析结果）。"""
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)
    items = serializers.ListField(
        child=serializers.DictField(),
        help_text="每项含 username/password/real_name/student_no/school 等字段",
    )
