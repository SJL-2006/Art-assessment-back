from rest_framework import serializers

from apps.classroom.models import ClassRoom, ClassStudent, ClassTeacher


class ClassRoomSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source="school.name", read_only=True)
    head_teacher_name = serializers.CharField(source="head_teacher.real_name", read_only=True)

    class Meta:
        model = ClassRoom
        fields = "__all__"


class ClassStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassStudent
        fields = "__all__"


class ClassTeacherSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassTeacher
        fields = "__all__"
