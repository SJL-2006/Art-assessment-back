"""批量生成 / 补齐学校编号（School.code）。

学生注册时用学校编号定位学校，因此每所学校都需要一个规范、唯一的编号。

用法：
    # 1) 预览：只打印将要生成的编号，不写库（默认）
    python manage.py gen_school_codes

    # 2) 只补齐编号为空/空白的学校
    python manage.py gen_school_codes --apply

    # 3) 全部重排（按学校 id 顺序重新编号，谨慎使用）
    python manage.py gen_school_codes --mode reassign --apply

    # 4) 自定义前缀与起始序号
    python manage.py gen_school_codes --prefix SC --start 101 --apply
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.org.models import School


class Command(BaseCommand):
    help = "批量生成/补齐学校编号（默认 dry-run，加 --apply 才写库）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply", action="store_true",
            help="实际写入数据库（不加则只预览）",
        )
        parser.add_argument(
            "--mode", choices=["fill", "reassign"], default="fill",
            help="fill=只补齐编号为空的学校（默认）；reassign=全部学校重排编号",
        )
        parser.add_argument("--prefix", default="SCH", help="编号前缀，默认 SCH")
        parser.add_argument("--start", type=int, default=1, help="起始序号，默认 1")
        parser.add_argument("--width", type=int, default=3, help="序号补零位数，默认 3")

    def handle(self, *args, **options):
        apply = options["apply"]
        mode = options["mode"]
        prefix = options["prefix"]
        start = options["start"]
        width = options["width"]

        def fmt(no: int) -> str:
            return f"{prefix}{no:0{width}d}"

        schools = list(School.objects.order_by("id"))
        if not schools:
            self.stdout.write(self.style.WARNING("没有学校数据，无需处理。"))
            return

        # 已被占用的编号（不含空白），fill 模式下要避开
        used = {(s.code or "").strip() for s in schools}
        used.discard("")

        plan = []  # [(school, old_code, new_code)]
        seq = start

        if mode == "reassign":
            for school in schools:
                plan.append((school, school.code, fmt(seq)))
                seq += 1
        else:
            for school in schools:
                old = (school.code or "").strip()
                if old:
                    continue
                while fmt(seq) in used:
                    seq += 1
                new_code = fmt(seq)
                used.add(new_code)
                seq += 1
                plan.append((school, old or "（空）", new_code))

        if not plan:
            self.stdout.write(self.style.SUCCESS(
                f"全部 {len(schools)} 所学校都已有编号，无需补齐。"
            ))
            return

        # 输出对照表
        self.stdout.write(f"模式：{mode}｜共 {len(schools)} 所学校，待处理 {len(plan)} 所")
        self.stdout.write("-" * 62)
        self.stdout.write(f"{'学校 ID':<8}{'学校名称':<24}{'原编号':<14}{'新编号':<14}")
        self.stdout.write("-" * 62)
        for school, old, new in plan:
            self.stdout.write(f"{school.id:<8}{school.name[:22]:<24}{str(old):<14}{new:<14}")
        self.stdout.write("-" * 62)

        if not apply:
            self.stdout.write(self.style.WARNING(
                "以上为预览，未写入数据库。确认无误后加 --apply 执行。"
            ))
            return

        with transaction.atomic():
            if mode == "reassign":
                # 两阶段：先把旧编号置为临时值，避免唯一约束冲突
                for school, _old, _new in plan:
                    School.objects.filter(pk=school.pk).update(code=f"__tmp__{school.pk}")
            for school, _old, new in plan:
                School.objects.filter(pk=school.pk).update(code=new)

        self.stdout.write(self.style.SUCCESS(f"已更新 {len(plan)} 所学校的编号。"))
