"""一次性测试数据脚本：创建管理员 + 行政区 + 学校，供接口测试使用。

用法：python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.dev'); import django; django.setup(); from scripts.seed import run; run()"
"""
import os


def run():
    from apps.users.models import User
    from apps.org.models import Region, School

    # 1. 省
    province, _ = Region.objects.get_or_create(
        code="510000",
        defaults={"name": "四川省", "level": Region.LEVEL_PROVINCE},
    )
    # 2. 市
    city, _ = Region.objects.get_or_create(
        code="510100",
        defaults={"name": "成都市", "level": Region.LEVEL_CITY, "parent": province},
    )
    # 3. 区县
    district, _ = Region.objects.get_or_create(
        code="510104",
        defaults={"name": "锦江区", "level": Region.LEVEL_DISTRICT, "parent": city},
    )
    # 4. 学校
    school, _ = School.objects.get_or_create(
        code="SCH001",
        defaults={
            "name": "锦江区实验小学",
            "region": district,
            "address": "锦江区某路1号",
            "contact": "张老师",
            "phone": "13800000000",
        },
    )
    # 5. 省级管理员
    u, _ = User.objects.get_or_create(
        username="admin_province",
        defaults={
            "role": User.ROLE_PROVINCE,
            "real_name": "省管理员",
            "region": province,
        },
    )
    u.set_password("123456")
    u.save()

    # 6. 学校管理员
    u, _ = User.objects.get_or_create(
        username="admin_school",
        defaults={
            "role": User.ROLE_SCHOOL,
            "real_name": "校管理员",
            "school": school,
            "region": district,
        },
    )
    u.set_password("123456")
    u.save()

    # 7. 教师
    u, _ = User.objects.get_or_create(
        username="teacher01",
        defaults={
            "role": User.ROLE_TEACHER,
            "real_name": "李老师",
            "school": school,
            "region": district,
        },
    )
    u.set_password("123456")
    u.save()

    # 8. 学生
    u, _ = User.objects.get_or_create(
        username="student01",
        defaults={
            "role": User.ROLE_STUDENT,
            "real_name": "王小明",
            "student_no": "S2024001",
            "school": school,
            "region": district,
        },
    )
    u.set_password("123456")
    u.save()

    print("✅ 测试数据已就绪")
    print("账号列表（密码均为 123456）：")
    for u in User.objects.filter(username__in=["admin_province", "admin_school", "teacher01", "student01"]):
        print(f"  {u.username}  role={u.role}")
