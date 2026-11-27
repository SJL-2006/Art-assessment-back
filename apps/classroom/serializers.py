"""班级相关序列化器。"""
from rest_framework import serializers

from apps.classroom.models import ClassCourse, ClassRoom, ClassStudent, ClassTeacher


class ClassRoomSerializer(serializers.ModelSerializer):
    """班级基础序列化器。"""
    code = serializers.CharField(required=False, allow_blank=True, max_length=64)
    school_name = serializers.CharField(source="school.name", read_only=True, default="")
    school_code = serializers.CharField(source="school.code", read_only=True, default="")
    head_teacher_name = serializers.CharField(source="head_teacher.real_name", read_only=True, default="")
    head_teacher_email = serializers.CharField(source="head_teacher.email", read_only=True, default="")
    student_count = serializers.IntegerField(read_only=True, required=False)
    is_my_head = serializers.BooleanField(read_only=True, required=False, default=False)
    is_my_subject = serializers.BooleanField(read_only=True, required=False, default=False)

    class Meta:
        model = ClassRoom
        fields = "__all__"


class ClassStudentSerializer(serializers.ModelSerializer):
    """班级-学生关系序列化器。"""
    student_username = serializers.CharField(source="student.username", read_only=True)
    student_real_name = serializers.CharField(source="student.real_name", read_only=True)
    student_no = serializers.CharField(source="student.student_no", read_only=True, default="")

    class Meta:
        model = ClassStudent
        fields = "__all__"


class ClassTeacherSerializer(serializers.ModelSerializer):
    """班级-教师关系序列化器。"""
    teacher_username = serializers.CharField(source="teacher.username", read_only=True)
    teacher_real_name = serializers.CharField(source="teacher.real_name", read_only=True)
    course_name = serializers.CharField(source="course.name", read_only=True, default="")

    class Meta:
        model = ClassTeacher
        fields = "__all__"


class ClassCourseSerializer(serializers.ModelSerializer):
    """班级课程序列化器。"""
    class_name = serializers.CharField(source="class_room.name", read_only=True, default="")
    course_name = serializers.CharField(source="course.name", read_only=True, default="")
    course_code = serializers.CharField(source="course.code", read_only=True, default="")
    course_description = serializers.CharField(source="course.description", read_only=True, default="")
    published_by_name = serializers.CharField(source="published_by.real_name", read_only=True, default="")

    class Meta:
        model = ClassCourse
        fields = (
            "id", "class_room", "class_name",
            "course", "course_name", "course_code", "course_description",
            "published_by", "published_by_name", "created_at",
        )


class JoinClassSerializer(serializers.Serializer):
    """学生申请加入班级。"""
    student_no = serializers.CharField(required=False, help_text="学生可选提交学籍号，供校验")


class ChangeClassSerializer(serializers.Serializer):
    """学生申请更换班级。"""
    target_class_id = serializers.IntegerField(help_text="目标班级 ID")
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class ApproveResultSerializer(serializers.Serializer):
    """审核通过/拒绝。"""
    approved = serializers.BooleanField(help_text="true=通过, false=拒绝")


class ImportStudentsSerializer(serializers.Serializer):
    """批量导入学生（传学生 ID / 学籍号 / 账号名列表）。"""
    student_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    student_nos = serializers.ListField(child=serializers.CharField(), required=False)
    usernames = serializers.ListField(child=serializers.CharField(), required=False)
