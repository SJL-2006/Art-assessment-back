"""seed_sichuan_cities：补充四川省 21 个市州行政区（可选创建市级管理员账号）。

用法示例：
    python manage.py seed_sichuan_cities --dry-run
    python manage.py seed_sichuan_cities
    python manage.py seed_sichuan_cities --with-accounts

只做 update_or_create 补全市州层级，不改 Region / School / User 模型、不需要迁移，
不影响现有成都市及其下属区县 / 学校 / 学生。
"""
import random

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand

from apps.common.management.commands.seed_chengdu_data import _gen_adult_names
from apps.org.models import Region
from apps.users.models import User

# 21 个市州级行政区（18 个地级市 + 3 个自治州），code 采用国家标准区划代码
SICHUAN_CITIES = [
    ("510100", "成都市"),
    ("510300", "自贡市"),
    ("510400", "攀枝花市"),
    ("510500", "泸州市"),
    ("510600", "德阳市"),
    ("510700", "绵阳市"),
    ("510800", "广元市"),
    ("510900", "遂宁市"),
    ("511000", "内江市"),
    ("511100", "乐山市"),
    ("511300", "南充市"),
    ("511400", "眉山市"),
    ("511500", "宜宾市"),
    ("511600", "广安市"),
    ("511700", "达州市"),
    ("511800", "雅安市"),
    ("511900", "巴中市"),
    ("512000", "资阳市"),
    ("513200", "阿坝藏族羌族自治州"),
    ("513300", "甘孜藏族自治州"),
    ("513400", "凉山彝族自治州"),
]

DEFAULT_PASSWORD = "123456"


class Command(BaseCommand):
    help = "补充四川省 21 个市州行政区（可选 --with-accounts 为新增市州创建 2 个市级管理员账号）。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="只统计将新增/更新的市州，不写库")
        parser.add_argument("--with-accounts", action="store_true", help="为每个新增市州创建 2 个市级管理员账号（默认不创建）")

    @staticmethod
    def _ensure_province():
        """确保省级节点存在（幂等），返回四川省 Region。"""
        province, _ = Region.objects.update_or_create(
            code="510000",
            defaults={
                "name": "四川省", "level": Region.LEVEL_PROVINCE, "parent": None,
                "is_deleted": False, "deleted_at": None,
            },
        )
        return province

    def _create_city_accounts(self, new_cities):
        """为每个新增市州创建 2 个市级管理员账号（成都市已存在，跳过）。"""
        password_hash = make_password(DEFAULT_PASSWORD)
        created = 0
        rows = []
        for code, _name in new_cities:
            city = Region.objects.get(code=code)
            rng = random.Random(f"edu-{code}-city-admin")
            names = _gen_adult_names(rng, 2)  # 同一市州两个账号不重名
            for i in range(2):
                username = f"edu_{code}_{i + 1:02d}"
                _, is_new = User.objects.update_or_create(
                    username=username,
                    defaults={
                        "role": User.ROLE_CITY,
                        "region": city,
                        "school": None,
                        "real_name": names[i],
                        "password": password_hash,
                        "is_active": True,
                        "is_staff": False,
                        "is_superuser": False,
                        "student_no": "",
                        "staff_no": "",
                    },
                )
                created += int(is_new)
                rows.append((username, names[i], city.name))
        self.stdout.write(self.style.SUCCESS(f"市级管理员账号：新增 {created} 个（共 {len(rows)} 个，密码 {DEFAULT_PASSWORD}）"))
        for username, real_name, city_name in rows:
            self.stdout.write(f"    {username} / {DEFAULT_PASSWORD}（{real_name} · {city_name}）")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        with_accounts = options["with_accounts"]

        province = self._ensure_province()

        new_cities = []
        existing_cities = []
        for code, name in SICHUAN_CITIES:
            (new_cities if not Region.objects.filter(code=code).exists() else existing_cities).append((code, name))

        self.stdout.write(self.style.SUCCESS("四川省市州补全：" + ("（--dry-run，未写库）" if dry_run else "")))
        self.stdout.write(f"  新增：{len(new_cities)} 个")
        existing_label = f"（{'、'.join(n for _, n in existing_cities)}）" if existing_cities else ""
        self.stdout.write(f"  已存在：{len(existing_cities)} 个{existing_label}")
        self.stdout.write(f"  市州总数：{len(SICHUAN_CITIES)}")

        if dry_run:
            if new_cities:
                self.stdout.write("  将新增：")
                for code, name in new_cities:
                    self.stdout.write(f"    {code}  {name}")
            if with_accounts:
                self.stdout.write(f"  （--with-accounts 将为上述 {len(new_cities)} 个新增市州各创建 2 个市级管理员账号）")
            return

        # 写入 21 个市州（update_or_create 按 code 幂等，成都市会更新为正确名称/层级/父级）
        for code, name in SICHUAN_CITIES:
            Region.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "level": Region.LEVEL_CITY,
                    "parent": province,
                    "is_deleted": False,
                    "deleted_at": None,
                },
            )
        self.stdout.write(self.style.SUCCESS("市州层级已写入完成。"))

        if with_accounts:
            self._create_city_accounts(new_cities)
        else:
            self.stdout.write("  未创建账号（如需市级管理员账号，加 --with-accounts）。")
