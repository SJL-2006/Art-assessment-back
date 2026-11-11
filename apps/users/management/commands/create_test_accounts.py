"""创建/重置各端测试账号（幂等）。

为每个角色（端）各建一个测试账号，密码统一已知，便于各端登录联调；
并补齐组织链（省→市→区县→学校）与学生班级，使账号可直接用于组卷/作答。
运行：python manage.py create_test_accounts
"""
from django.core.management.base import BaseCommand

from apps.classroom.models import APPROVED, ClassRoom, ClassStudent
from apps.org.models import Region, School
from apps.users.models import User

# username, role, real_name, password, 是否超级用户, 编号(学生=学号, 教职工=职工编号)
ACCOUNTS = [
    ("admin", User.ROLE_QB_ADMIN, "题库管理员", "admin123456", True, "STAFF000"),
    ("teacher", User.ROLE_TEACHER, "李老师", "teacher123456", False, "STAFF001"),
    ("student", User.ROLE_STUDENT, "小明", "student123456", False, "S2024001"),
    ("school", User.ROLE_SCHOOL, "校管理员", "school123456", False, "STAFF002"),
    ("district", User.ROLE_DISTRICT, "区县管理员", "district123456", False, "STAFF003"),
    ("city", User.ROLE_CITY, "市州管理员", "city123456", False, "STAFF004"),
    ("province", User.ROLE_PROVINCE, "省级管理员", "province123456", False, "STAFF005"),
]


class Command(BaseCommand):
    help = "创建/重置各端测试账号（每个角色一个，幂等）"

    def handle(self, *args, **options):
        # 1) 组织链：省 → 市 → 区县 → 学校
        province, _ = Region.objects.get_or_create(
            code="510000", defaults={"name": "四川省", "level": Region.LEVEL_PROVINCE},
        )
        city, _ = Region.objects.get_or_create(
            code="510100", defaults={"name": "成都市", "level": Region.LEVEL_CITY, "parent": province},
        )
        district, _ = Region.objects.get_or_create(
            code="510104", defaults={"name": "锦江区", "level": Region.LEVEL_DISTRICT, "parent": city},
        )
        school, _ = School.objects.get_or_create(
            code="SCH001", defaults={"name": "锦江区实验小学", "region": district},
        )

        # 2) 各端账号（幂等：已存在则重置角色/密码/组织，不重复建号）
        self.stdout.write(self.style.SUCCESS("各端测试账号（密码如下）："))
        for username, role, real_name, password, is_super, number in ACCOUNTS:
            user, created = User.objects.get_or_create(username=username, defaults={"role": role})
            user.role = role
            user.real_name = real_name
            user.is_active = True
            if is_super:
                user.is_superuser = True
                user.is_staff = True
            if role in (User.ROLE_TEACHER, User.ROLE_STUDENT, User.ROLE_SCHOOL):
                user.school = school
                user.region = district
            elif role == User.ROLE_DISTRICT:
                user.region = district
            elif role == User.ROLE_CITY:
                user.region = city
            elif role == User.ROLE_PROVINCE:
                user.region = province
            # 编号：学生写入学号，教职工写入职工编号
            if role == User.ROLE_STUDENT:
                user.student_no = number
            else:
                user.staff_no = number
            user.set_password(password)
            user.save()
            tag = "新建" if created else "已存在·重置"
            self.stdout.write(f"  {username:<10} {role:<10} {password:<16} {number:<12} {tag}")

        # 3) 学生挂班级（年级=三年级），使练习/组卷按年级可抽题。
        #    用 filter+first 而非 get_or_create，规避历史重复 ClassStudent 记录。
        klass, _ = ClassRoom.objects.get_or_create(
            code="CLS001", defaults={"name": "三年级一班", "grade": "三年级", "school": school},
        )
        student = User.objects.filter(username="student").first()
        if student:
            rel = ClassStudent.objects.filter(klass=klass, student=student).first()
            if rel is None:
                ClassStudent.objects.create(klass=klass, student=student, status=APPROVED)
            elif rel.status != APPROVED:
                rel.status = APPROVED
                rel.save(update_fields=["status"])

        self.stdout.write(self.style.SUCCESS("完成：组织链 四川省→成都市→锦江区→锦江区实验小学，学生「小明」已入「三年级一班」。"))
