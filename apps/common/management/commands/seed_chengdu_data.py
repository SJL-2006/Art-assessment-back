"""seed_chengdu_data：初始化成都市中小学真实数据（幂等、可续跑）。

用法示例：
    python manage.py seed_chengdu_data --dry-run
    python manage.py seed_chengdu_data --limit 3
    python manage.py seed_chengdu_data --districts 510104,510105
    python manage.py seed_chengdu_data --reset --yes

只做数据初始化，不改前端、不改现有接口、不生成试卷/成绩/答卷。
"""
import random

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.classroom.models import APPROVED, ClassRoom, ClassStudent, ClassTeacher
from apps.common.seed_data.chengdu_schools import (
    ADULT_FEMALE_GIVEN,
    ADULT_MALE_GIVEN,
    DIRECTLY_AFFILIATED,
    REGIONS,
    SCHOOLS,
    STUDENT_FEMALE_GIVEN,
    STUDENT_MALE_GIVEN,
    SURNAMES,
    TYPE_GRADES,
)
from apps.org.models import Region, School
from apps.questionbank.models import Course
from apps.users.models import User

# 年级 -> 班号中的年级序号（一年级=01 ... 九年级=09，高一=10、高二=11、高三=12）
GRADE_NO = {
    "一年级": 1, "二年级": 2, "三年级": 3, "四年级": 4, "五年级": 5, "六年级": 6,
    "七年级": 7, "八年级": 8, "九年级": 9,
    "高一": 10, "高二": 11, "高三": 12,
}

CHINESE_NUM = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

# 管理端固定账号（用户名 -> (姓名, role)）；region 在运行时再挂。
FIXED_ADMINS = [
    ("edu_sc_01", "王建国", User.ROLE_PROVINCE),
    ("edu_sc_02", "李慧敏", User.ROLE_PROVINCE),
    ("edu_cd_01", "张明远", User.ROLE_CITY),
    ("edu_cd_02", "刘晓梅", User.ROLE_CITY),
    ("qbadmin_01", "陈文博", User.ROLE_QB_ADMIN),
    ("qbadmin_02", "周雅琴", User.ROLE_QB_ADMIN),
]


def _class_display_name(grade, class_no):
    """班级名称：小学/初中用中文数字，高中用（1）班。"""
    if grade.startswith("高"):
        return f"{grade}（{class_no}）班"
    if 1 <= class_no <= 10:
        return f"{grade}{CHINESE_NUM[class_no - 1]}班"
    return f"{grade}{class_no}班"


def _gen_student_names(rng, count):
    """确定性生成学生姓名：姓氏 + 双字名为主、少量单字名；同一班级内去重。"""
    names = []
    seen = set()
    while len(names) < count:
        surname = rng.choice(SURNAMES)
        given = rng.choice(STUDENT_FEMALE_GIVEN if rng.random() < 0.5 else STUDENT_MALE_GIVEN)
        if rng.random() < 0.1:  # 少量单字名
            given = given[0]
        name = surname + given
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _gen_adult_names(rng, count):
    """确定性生成成人姓名（教师 / 管理员）。"""
    names = []
    seen = set()
    while len(names) < count:
        surname = rng.choice(SURNAMES)
        given = rng.choice(ADULT_FEMALE_GIVEN if rng.random() < 0.5 else ADULT_MALE_GIVEN)
        name = surname + given
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def _expand_schools():
    """按 REGIONS 顺序展开全部学校，附带全局序号与区县内序号。"""
    result = []
    seq = 0
    for region_code, _name in REGIONS:
        for idx, (school_name, stype) in enumerate(SCHOOLS[region_code], start=1):
            seq += 1
            result.append({
                "region_code": region_code,
                "name": school_name,
                "type": stype,
                "school_seq": seq,       # 全校全局顺序号（学号/工号里的学校ID）
                "region_index": idx,     # 区县内顺序号（决定 School.code 后三位）
            })
    return result


class Command(BaseCommand):
    help = "初始化成都市 226 所真实中小学的行政区、学校、班级、师生与管理端账号。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="只统计并打印将要生成的数量，不写库")
        parser.add_argument("--limit", type=int, default=None, help="只处理前 N 所学校（联调用）")
        parser.add_argument("--districts", type=str, default=None, help="只处理指定区县（code 或中文名，逗号分隔）")
        parser.add_argument("--classes-per-grade", type=int, default=2, help="每年级班数，默认 2，范围 1-8")
        parser.add_argument("--students-per-class", type=int, default=45, help="每班基准人数，默认 45，范围 20-60，实际浮动 ±3")
        parser.add_argument("--password", type=str, default="123456", help="统一初始密码，默认 123456")
        parser.add_argument("--reset", action="store_true", help="删除本命令之前生成的数据后重建（必须同时传 --yes）")
        parser.add_argument("--yes", action="store_true", help="确认执行 --reset")

    # ---------------- 范围与统计 ----------------

    def _filter_scope(self, expanded, districts, limit):
        scope = list(expanded)
        if districts:
            allowed = set()
            name_to_code = {name: code for code, name in REGIONS}
            code_set = {code for code, _ in REGIONS}
            for token in (t.strip() for t in districts.split(",") if t.strip()):
                if token in name_to_code:
                    allowed.add(name_to_code[token])
                elif token in code_set:
                    allowed.add(token)
                else:
                    raise CommandError(f"未知区县：{token}")
            scope = [e for e in scope if e["region_code"] in allowed]
        if limit:
            scope = scope[:limit]
        return scope

    @staticmethod
    def _school_code(entry):
        return f"{entry['region_code']}{entry['region_index']:03d}"

    def _scope_school_codes(self, scope):
        return [self._school_code(e) for e in scope]

    def _reset_admin_usernames(self, scope):
        usernames = []
        district_codes = {e["region_code"] for e in scope}
        for code, _name in REGIONS:
            if code in district_codes:
                usernames += [f"edu_{code}_01", f"edu_{code}_02"]
        usernames += ["edu_sc_01", "edu_sc_02", "edu_cd_01", "edu_cd_02", "qbadmin_01", "qbadmin_02"]
        return usernames

    def _print_reset_preview(self, scope):
        codes = self._scope_school_codes(scope)
        schools_qs = School.objects.filter(code__in=codes)
        school_count = schools_qs.count()
        user_count = User.objects.filter(school__in=schools_qs).count()
        class_count = ClassRoom.objects.filter(school__in=schools_qs).count()
        admin_count = User.objects.filter(username__in=self._reset_admin_usernames(scope)).count()
        self.stdout.write(self.style.WARNING(
            f"即将删除：学校 {school_count} 所、班级 {class_count} 个、"
            f"师生/学校管理员账号 {user_count} 个、管理端账号 {admin_count} 个"
        ))

    def _do_reset(self, scope):
        codes = self._scope_school_codes(scope)
        schools_qs = School.objects.filter(code__in=codes)
        # 分批删除师生/学校管理员：避免单条 IN 语句变量数超限（SQLite/MySQL 均有上限）
        user_ids = list(
            User.objects.filter(school__in=schools_qs).values_list("id", flat=True)
        )
        for i in range(0, len(user_ids), 500):
            User.objects.filter(id__in=user_ids[i:i + 500]).delete()
        schools_qs.delete()  # 级联删除班级 / ClassStudent / ClassTeacher
        User.objects.filter(username__in=self._reset_admin_usernames(scope)).delete()

    # ---------------- 单个学校 ----------------

    def _ensure_school_admin(self, school, region, password_hash):
        rng = random.Random(f"{school.code}-admin")
        real_name = _gen_adult_names(rng, 1)[0]
        User.objects.update_or_create(
            username=f"sch_{school.code}",
            defaults={
                "role": User.ROLE_SCHOOL, "school": school, "region": region,
                "real_name": real_name, "password": password_hash, "is_active": True,
                "is_staff": False, "is_superuser": False, "student_no": "", "staff_no": "",
            },
        )

    def _process_school(self, entry, region_map, music_course, art_course, password_hash, cpg, spc, now):
        """处理一所学校：建校、建教师、建班级、建学生。返回统计或 None（跳过）。"""
        region = region_map[entry["region_code"]]
        school_name = entry["name"]
        school_type = entry["type"]
        school_seq = entry["school_seq"]
        code = self._school_code(entry)

        existing = School.objects.filter(name=school_name, region=region, is_deleted=False).first()
        if existing is not None and existing.code != code:
            self.stdout.write(self.style.WARNING(
                f"跳过 {school_name}：已存在同名学校但编号不同（现为 {existing.code}，期望 {code}）"
            ))
            return None
        if existing is None:
            school, _created = School.objects.update_or_create(
                code=code,
                defaults={
                    "name": school_name, "region": region,
                    "address": "", "contact": "", "phone": "",
                    "is_directly_affiliated": school_name in DIRECTLY_AFFILIATED,
                },
            )
        else:
            school = existing

        expected_da = school_name in DIRECTLY_AFFILIATED
        if school.is_directly_affiliated != expected_da:
            school.is_directly_affiliated = expected_da
            school.save(update_fields=["is_directly_affiliated"])

        # 学校管理员账号始终确保存在
        self._ensure_school_admin(school, region, password_hash)

        # 已有班级则跳过班级/学生生成（幂等）
        if ClassRoom.objects.filter(school=school, is_deleted=False).exists():
            return {"school": school, "reused": True}

        # 展开班级
        class_entries = []
        global_no = 0
        for grade in TYPE_GRADES[school_type]:
            grade_no = GRADE_NO[grade]
            for class_no in range(1, cpg + 1):
                global_no += 1
                class_entries.append({
                    "grade": grade,
                    "grade_no": grade_no,
                    "class_no": class_no,
                    "global_no": global_no,
                    "code": f"{code}-{grade_no:02d}{class_no:02d}",
                    "name": _class_display_name(grade, class_no),
                })
        class_total = len(class_entries)

        # 教师：音乐 2、美术 2、班主任 = 班级总数
        rng_teacher = random.Random(f"{code}-teacher")
        teacher_names = _gen_adult_names(rng_teacher, 4 + class_total)
        music_names = teacher_names[0:2]
        art_names = teacher_names[2:4]
        head_names = teacher_names[4:]

        staff_seq = 0

        def build_teacher(real_name, teacher_type, teacher_subject):
            nonlocal staff_seq
            staff_seq += 1
            staff_no = f"{school_seq:05d}{staff_seq:03d}"
            return User(
                username=staff_no, role=User.ROLE_TEACHER, real_name=real_name,
                staff_no=staff_no, student_no="", school=school, region=region,
                teacher_type=teacher_type, teacher_subject=teacher_subject,
                password=password_hash, is_active=True, is_staff=False, is_superuser=False,
                date_joined=now,
            )

        music_users = [build_teacher(n, User.TEACHER_TYPE_SUBJECT, "music") for n in music_names]
        art_users = [build_teacher(n, User.TEACHER_TYPE_SUBJECT, "art") for n in art_names]
        head_users = [
            build_teacher(n, User.TEACHER_TYPE_HEAD, "music" if i % 2 == 0 else "art")
            for i, n in enumerate(head_names)
        ]
        teacher_objs = music_users + art_users + head_users
        User.objects.bulk_create(teacher_objs, batch_size=500)
        staff_nos = [u.username for u in teacher_objs]
        teacher_id_map = {u.username: u.id for u in User.objects.filter(username__in=staff_nos)}

        # 班级 + 班主任
        class_objs = [
            ClassRoom(
                name=ce["name"], code=ce["code"], grade=ce["grade"],
                school=school, head_teacher_id=teacher_id_map[head_users[i].username],
            )
            for i, ce in enumerate(class_entries)
        ]
        ClassRoom.objects.bulk_create(class_objs, batch_size=500)
        klass_id_map = {
            c.code: c.id for c in ClassRoom.objects.filter(code__in=[ce["code"] for ce in class_entries])
        }

        # 任课：每班音乐、美术各 1 条（4 名教师轮流分配）
        ct_objs = []
        for i, ce in enumerate(class_entries):
            m = music_users[i % 2]
            a = art_users[i % 2]
            ct_objs.append(ClassTeacher(
                klass_id=klass_id_map[ce["code"]], teacher_id=teacher_id_map[m.username],
                course=music_course, status=APPROVED,
            ))
            ct_objs.append(ClassTeacher(
                klass_id=klass_id_map[ce["code"]], teacher_id=teacher_id_map[a.username],
                course=art_course, status=APPROVED,
            ))
        ClassTeacher.objects.bulk_create(ct_objs, batch_size=500)

        # 学生 + ClassStudent
        student_count = 0
        for ce in class_entries:
            klass_id = klass_id_map[ce["code"]]
            rng = random.Random(f"{code}-{ce['code']}")
            size = max(1, min(spc + rng.randint(-3, 3), 60))
            names = _gen_student_names(rng, size)
            stu_objs = [
                User(
                    username=f"{school_seq:05d}{ce['global_no']:02d}{seat:02d}",
                    role=User.ROLE_STUDENT, real_name=names[seat - 1],
                    student_no=f"{school_seq:05d}{ce['global_no']:02d}{seat:02d}",
                    staff_no="", school=school, region=region,
                    password=password_hash, is_active=True, is_staff=False, is_superuser=False,
                    date_joined=now,
                )
                for seat in range(1, size + 1)
            ]
            User.objects.bulk_create(stu_objs, batch_size=500)
            stu_nos = [o.username for o in stu_objs]
            stu_id_map = {u.username: u.id for u in User.objects.filter(username__in=stu_nos)}
            ClassStudent.objects.bulk_create(
                [ClassStudent(klass_id=klass_id, student_id=stu_id_map[n], status=APPROVED) for n in stu_nos],
                batch_size=500,
            )
            student_count += size

        return {
            "school": school,
            "class_count": class_total,
            "student_count": student_count,
            "teacher_count": 4 + class_total,
            "reused": False,
        }

    # ---------------- 管理端账号 ----------------

    def _ensure_admin_accounts(self, scope, region_map, province, city, password_hash):
        for username, real_name, role in FIXED_ADMINS:
            region = city if role == User.ROLE_CITY else province
            User.objects.update_or_create(
                username=username,
                defaults={
                    "role": role, "region": region, "school": None,
                    "real_name": real_name, "password": password_hash, "is_active": True,
                    "is_staff": False, "is_superuser": False,
                },
            )
        for code in sorted({e["region_code"] for e in scope}):
            region = region_map[code]
            rng = random.Random(f"edu-{code}-admin")
            names = _gen_adult_names(rng, 2)
            for i in range(2):
                User.objects.update_or_create(
                    username=f"edu_{code}_{i + 1:02d}",
                    defaults={
                        "role": User.ROLE_DISTRICT, "region": region, "school": None,
                        "real_name": names[i], "password": password_hash, "is_active": True,
                        "is_staff": False, "is_superuser": False,
                    },
                )

    # ---------------- 主流程 ----------------

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        districts = options["districts"]
        cpg = options["classes_per_grade"]
        spc = options["students_per_class"]
        password = options["password"]
        reset = options["reset"]
        yes = options["yes"]

        if not (1 <= cpg <= 8):
            raise CommandError("--classes-per-grade 取值范围为 1-8")
        if not (20 <= spc <= 60):
            raise CommandError("--students-per-class 取值范围为 20-60")

        expanded = _expand_schools()
        scope = self._filter_scope(expanded, districts, limit)
        if not scope:
            raise CommandError("没有匹配的学校")

        # 统计（dry-run 不写库，先统计后退出）
        total_schools = len(scope)
        total_classes = sum(len(TYPE_GRADES[e["type"]]) * cpg for e in scope)
        est_students = total_classes * spc
        est_teachers = total_schools * 4 + total_classes
        district_count = len({e["region_code"] for e in scope})
        est_accounts = est_students + est_teachers + total_schools + district_count * 2 + 6

        if dry_run:
            self.stdout.write(self.style.SUCCESS("== dry-run（不写库） =="))
            self.stdout.write(f"  学校：{total_schools} 所")
            self.stdout.write(f"  班级：{total_classes} 个（每年级 {cpg} 个班）")
            self.stdout.write(f"  学生：约 {est_students} 人（每班基准 {spc} 人，实际 ±3）")
            self.stdout.write(f"  教师：约 {est_teachers} 人（每校 4 名音乐/美术 + 每班 1 名班主任）")
            self.stdout.write(f"  学校管理员：{total_schools} 个")
            self.stdout.write(f"  区县管理员：{district_count * 2} 个")
            self.stdout.write(f"  市/省/题库管理员：各 2 个")
            self.stdout.write(f"  总账号：约 {est_accounts} 个")
            return

        password_hash = make_password(password)  # 只算一次，批量复用
        now = timezone.now()

        # 行政区 / 课程（幂等）
        province, _ = Region.objects.get_or_create(
            code="510000", defaults={"name": "四川省", "level": Region.LEVEL_PROVINCE, "parent": None},
        )
        city, _ = Region.objects.get_or_create(
            code="510100", defaults={"name": "成都市", "level": Region.LEVEL_CITY, "parent": province},
        )
        region_map = {}
        for code, name in REGIONS:
            region_map[code], _ = Region.objects.get_or_create(
                code=code, defaults={"name": name, "level": Region.LEVEL_DISTRICT, "parent": city},
            )
        music_course, _ = Course.objects.get_or_create(name="音乐", defaults={"code": "music"})
        art_course, _ = Course.objects.get_or_create(name="美术", defaults={"code": "art"})

        if reset:
            if not yes:
                self._print_reset_preview(scope)
                raise CommandError("--reset 必须同时传 --yes 确认（上面列出了将被删除的数量）")
            self.stdout.write(self.style.WARNING("开始清理本命令此前生成的数据……"))
            self._do_reset(scope)

        # 逐校处理
        stats = {"schools": 0, "reused": 0, "skipped": 0, "classes": 0, "students": 0, "teachers": 0}
        for i, entry in enumerate(scope, start=1):
            with transaction.atomic():
                result = self._process_school(
                    entry, region_map, music_course, art_course, password_hash, cpg, spc, now,
                )
            if result is None:
                stats["skipped"] += 1
                continue
            stats["schools"] += 1
            if result.get("reused"):
                stats["reused"] += 1
            else:
                stats["classes"] += result["class_count"]
                stats["students"] += result["student_count"]
                stats["teachers"] += result["teacher_count"]
            if i % 10 == 0:
                self.stdout.write(f"  已处理 {i}/{total_schools} 所学校……")

        # 管理端账号
        self._ensure_admin_accounts(scope, region_map, province, city, password_hash)

        # 汇总
        self.stdout.write(self.style.SUCCESS("== 完成 =="))
        self.stdout.write(f"  学校：{stats['schools']} 所（复用 {stats['reused']}，跳过 {stats['skipped']}）")
        self.stdout.write(f"  班级：{stats['classes']} 个")
        self.stdout.write(f"  学生：{stats['students']} 人")
        self.stdout.write(f"  教师：{stats['teachers']} 人")
        self.stdout.write(f"  学校管理员：{stats['schools']} 个")
        self.stdout.write(f"  区县管理员：{district_count * 2} 个")
        self.stdout.write(f"  市/省/题库管理员：各 2 个")
        self.stdout.write(f"  全部账号密码：{password}")

        # 示例账号（取范围内第一所学校）
        first_code = self._school_code(scope[0])
        first_school = School.objects.filter(code=first_code).first()
        if first_school:
            stu = User.objects.filter(school=first_school, role=User.ROLE_STUDENT).first()
            teacher = User.objects.filter(school=first_school, role=User.ROLE_TEACHER).first()
            sch_admin = User.objects.filter(username=f"sch_{first_code}").first()
            self.stdout.write("== 示例账号 ==")
            if stu:
                self.stdout.write(f"  学生：{stu.username} / {password}（{stu.real_name}）")
            if teacher:
                self.stdout.write(f"  教师：{teacher.username} / {password}（{teacher.real_name}）")
            if sch_admin:
                self.stdout.write(f"  学校管理员：{sch_admin.username} / {password}（{sch_admin.real_name}）")
