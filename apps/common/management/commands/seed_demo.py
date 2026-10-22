"""初始化演示数据（幂等）：账号 + 组织 + 班级 + 题库 + 已发布试卷。

覆盖 A/B/C 三模块测试所需的完整数据链，用于 Apifox 联调。
运行：python manage.py seed_demo
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.classroom.models import APPROVED, ClassRoom, ClassStudent
from apps.exam.models import Paper, PaperPublish, PaperQuestion
from apps.org.models import Region, School
from apps.questionbank.models import Course, Question
from apps.users.models import User


class Command(BaseCommand):
    help = "初始化演示数据（幂等），覆盖账号/组织/班级/题库/已发布试卷"

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) 行政区 → 学校 → 班级
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
            code="SCH001", defaults={"name": "测试小学", "region": district},
        )
        klass, _ = ClassRoom.objects.get_or_create(
            code="CLS001", defaults={"name": "三年级一班", "grade": "三年级", "school": school},
        )

        # 2) 各角色账号（幂等，重复运行会重置角色与密码）
        def make_user(username, role, real_name, password, **extra):
            user, _ = User.objects.get_or_create(username=username, defaults={"role": role})
            user.role = role
            user.real_name = real_name
            for key, value in extra.items():
                setattr(user, key, value)
            user.is_active = True
            user.set_password(password)
            user.save()
            return user

        admin = make_user("admin", User.ROLE_QB_ADMIN, "题库管理员", "admin123456")
        admin.is_staff = True
        admin.is_superuser = True
        admin.save()

        teacher = make_user(
            "teacher", User.ROLE_TEACHER, "李老师", "teacher123456", school=school, region=district,
        )
        student = make_user(
            "student", User.ROLE_STUDENT, "小明", "student123456",
            school=school, region=district, student_no="S2024001",
        )
        make_user("school", User.ROLE_SCHOOL, "校管理员", "school123456", school=school, region=district)
        make_user("district", User.ROLE_DISTRICT, "区县管理员", "district123456", region=district)
        make_user("city", User.ROLE_CITY, "市州管理员", "city123456", region=city)
        make_user("province", User.ROLE_PROVINCE, "省级管理员", "province123456", region=province)

        # 3) 学生加入班级（已通过审核）
        ClassStudent.objects.get_or_create(klass=klass, student=student, defaults={"status": APPROVED})

        # 4) 课程 + 试题（4 道客观题，全部已审核）
        music, _ = Course.objects.get_or_create(name="音乐", defaults={"code": "music"})
        Course.objects.get_or_create(name="美术", defaults={"code": "art"})

        question_specs = [
            ("single", "以下哪个是高音谱号？", [{"key": "A", "text": "𝄞"}, {"key": "B", "text": "𝄢"}, {"key": "C", "text": "𝄡"}, {"key": "D", "text": "𝄣"}], "A"),
            ("single", "四分音符的时值相当于几个八分音符？", [{"key": "A", "text": "1个"}, {"key": "B", "text": "2个"}, {"key": "C", "text": "3个"}, {"key": "D", "text": "4个"}], "B"),
            ("multiple", "下列哪些属于西洋乐器？", [{"key": "A", "text": "小提琴"}, {"key": "B", "text": "二胡"}, {"key": "C", "text": "钢琴"}, {"key": "D", "text": "长笛"}], "ACD"),
            ("judge", "标准音 a1 的频率是 440Hz。", [], "正确"),
        ]
        for qtype, stem, opts, answer in question_specs:
            Question.objects.get_or_create(
                course=music,
                stem=stem,
                defaults={
                    "qtype": qtype,
                    "difficulty": "easy",
                    "grade": "三年级",
                    "options": opts,
                    "answer": answer,
                    "status": Question.STATUS_APPROVED,
                    "creator": admin,
                },
            )

        # 5) 试卷 + 题目关联 + 发布（scope=class 命中「三年级一班」）
        paper, _ = Paper.objects.get_or_create(
            title="三年级音乐正式测评",
            defaults={
                "ptype": Paper.TYPE_FORMAL,
                "subject": Paper.SUBJECT_MUSIC,
                "level": Paper.LEVEL_CLASS,
                "grade": "三年级",
                "duration": 30,
                "total_score": Decimal("20"),
                "status": Paper.STATUS_PUBLISHED,
                "creator": admin,
            },
        )
        paper_qs = Question.objects.filter(
            course=music, status=Question.STATUS_APPROVED, stem__in=[s[1] for s in question_specs],
        ).order_by("id")
        for index, question in enumerate(paper_qs):
            PaperQuestion.objects.get_or_create(
                paper=paper, question=question, defaults={"sort": index + 1, "score": Decimal("5")},
            )

        publish, _ = PaperPublish.objects.get_or_create(
            paper=paper,
            scope_type=PaperPublish.SCOPE_CLASS,
            defaults={"target_class": klass, "target_school": school, "status": PaperPublish.STATUS_PUBLISHED},
        )
        publish.target_class = klass
        publish.target_school = school
        publish.status = PaperPublish.STATUS_PUBLISHED
        publish.save()

        self.stdout.write(self.style.SUCCESS("演示数据初始化完成。"))
        self.stdout.write("账号（角色 · 密码）：")
        self.stdout.write("  admin    / admin123456    （超级用户 · 题库管理员，可访问全部接口）")
        self.stdout.write("  teacher  / teacher123456  （教师，可评分/查看学生/导出）")
        self.stdout.write("  student  / student123456  （学生，已加入「三年级一班」）")
        self.stdout.write("  school   / school123456   （学校管理员，可统计）")
        self.stdout.write("  district / district123456 （区县管理员，可统计）")
        self.stdout.write("  city     / city123456     （市州管理员，可统计）")
        self.stdout.write("  province / province123456 （省级管理员，可统计+参与率导出）")
        self.stdout.write("数据链：四川省 → 成都市 → 锦江区 → 测试小学 → 三年级一班 → 小明")
        self.stdout.write("已发布试卷：三年级音乐正式测评（formal，总分 20，scope=class，4 道客观题）")
