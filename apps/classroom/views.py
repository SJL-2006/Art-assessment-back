from apps.classroom.models import ClassRoom, ClassStudent, ClassTeacher
from apps.classroom.serializers import (
    ClassRoomSerializer,
    ClassStudentSerializer,
    ClassTeacherSerializer,
)
from apps.common.views import BaseViewSet


class ClassRoomViewSet(BaseViewSet):
    """班级 CRUD。"""
    queryset = ClassRoom.objects.all()
    serializer_class = ClassRoomSerializer
    search_fields = ["name", "code"]
    ordering_fields = ["id"]

    def get_queryset(self):
        qs = super().get_queryset()
        school = self.request.query_params.get("school")
        if school:
            qs = qs.filter(school_id=school)
        return qs


class ClassStudentViewSet(BaseViewSet):
    """班级学生关系。"""
    queryset = ClassStudent.objects.all()
    serializer_class = ClassStudentSerializer


class ClassTeacherViewSet(BaseViewSet):
    """班级教师关系。"""
    queryset = ClassTeacher.objects.all()
    serializer_class = ClassTeacherSerializer
