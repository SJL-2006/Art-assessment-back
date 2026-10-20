"""重置所有 A 模块测试数据。"""
from django.core.management.base import BaseCommand
from django.db.models import Q


class Command(BaseCommand):
    help = "清掉所有测试数据并重新 seed"

    def handle(self, *args, **options):
        # 反向按外键依赖顺序删除
        from apps.classroom.models import ClassStudent, ClassTeacher, ClassRoom
        from apps.org.models import Region, School
        from apps.users.models import User
        from apps.common.models import OperationLog

        # 班级关系
        ClassStudent.objects.all().delete()
        ClassTeacher.objects.all().delete()
        ClassRoom.objects.all().delete()
        # 用户（学生/教师/学校/区县/市/省管理员/题库管理员，不删 Django 超级用户）
        User.objects.filter(Q(is_staff=False) & Q(is_superuser=False)).delete()
        # 学校、行政区
        School.objects.all().delete()
        Region.objects.all().delete()
        # 日志
        OperationLog.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("已清空旧数据"))

        # 重新 seed
        province = Region.objects.create(name="四川省", code="510000", level=Region.LEVEL_PROVINCE)
        city = Region.objects.create(name="成都市", code="510100", level=Region.LEVEL_CITY, parent=province)
        district = Region.objects.create(name="锦江区", code="510104", level=Region.LEVEL_DISTRICT, parent=city)
        school = School.objects.create(name="锦江区实验小学", code="SCH001", region=district, address="锦江区某路1号")

        def make_user(username, role, real_name, **kw):
            u = User(username=username, role=role, real_name=real_name, **kw)
            u.set_password("123456")
            u.save()
            return u

        make_user("admin_province", User.ROLE_PROVINCE, "省管理员", region=province)
        make_user("admin_school", User.ROLE_SCHOOL, "校管理员", school=school, region=district)
        make_user("teacher01", User.ROLE_TEACHER, "李老师", school=school, region=district)
        make_user("student01", User.ROLE_STUDENT, "王小明", school=school, region=district, student_no="S2024001")

        self.stdout.write(self.style.SUCCESS("✅ 测试数据已就绪，密码均为 123456"))
