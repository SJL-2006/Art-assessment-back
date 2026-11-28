"""backfill_teacher_subject：为现有教师账号回填任教学科（music/art）。

用法示例：
    python manage.py backfill_teacher_subject --dry-run
    python manage.py backfill_teacher_subject --apply
    python manage.py backfill_teacher_subject --apply --fix

只写 User.teacher_subject（可选 --fix 软删除跨学科 ClassTeacher），不改模型、不建账号、不删教师。
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.classroom.models import APPROVED, ClassTeacher
from apps.users.models import User


class Command(BaseCommand):
    help = "回填教师任教学科（teacher_subject），可选 --fix 清理跨学科 ClassTeacher。"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="只打印分配结果，不写库")
        parser.add_argument("--apply", action="store_true", help="实际写库")
        parser.add_argument("--fix", action="store_true", help="软删除跨学科教师另一学科的 ClassTeacher 记录（需配合 --apply）")

    @staticmethod
    def _subject_counts(teacher):
        """统计该教师已通过（approved）的 ClassTeacher 按 course.code 的班级数。"""
        codes = ClassTeacher.objects.filter(
            teacher=teacher, is_deleted=False, status=APPROVED,
            course__code__in=["music", "art"],
        ).values_list("course__code", flat=True)
        return Counter(codes)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        apply = options["apply"]
        fix = options["fix"]

        teachers = User.objects.filter(role=User.ROLE_TEACHER).order_by("id")
        already = 0
        filled = 0
        conflict = 0

        # plans: list of (teacher, subject, other_codes)
        plans = []
        for t in teachers:
            if t.teacher_subject:
                already += 1
                continue
            counts = self._subject_counts(t)
            if not counts:
                # 无 ClassTeacher 的班主任：按 id 确定性分配
                subject = "music" if t.id % 2 == 0 else "art"
                plans.append((t, subject, []))
                filled += 1
            elif len(counts) == 1:
                subject = next(iter(counts))
                plans.append((t, subject, []))
                filled += 1
            else:
                subject = counts.most_common(1)[0][0]
                other = [c for c in counts if c != subject]
                plans.append((t, subject, other))
                conflict += 1

        self.stdout.write(self.style.SUCCESS("教师任教学科回填：" + ("（--dry-run，未写库）" if dry_run else "")))
        self.stdout.write(f"  已是单学科：{already} 人")
        self.stdout.write(f"  已补齐：{filled} 人")
        self.stdout.write(f"  发现跨学科：{conflict} 人")
        if conflict:
            for t, subject, other in plans:
                if not other:
                    continue
                self.stdout.write(f"    {t.real_name or t.username}（#{t.id}）取 {subject}，另一学科 {','.join(other)}")
        self.stdout.write(f"  未处理：{teachers.count() - already - filled - conflict} 人")

        if dry_run:
            if fix:
                self.stdout.write(self.style.WARNING("  （--fix 将为上述跨学科教师软删除另一学科的 ClassTeacher 记录）"))
            return

        if not apply:
            self.stdout.write(self.style.WARNING("未传 --apply，未写库。如需写入请加 --apply。"))
            return

        for t, subject, other in plans:
            t.teacher_subject = subject
            t.save(update_fields=["teacher_subject"])

        fixed = 0
        if fix and conflict:
            for t, subject, other in plans:
                if not other:
                    continue
                deleted = ClassTeacher.objects.filter(
                    teacher=t, is_deleted=False, course__code__in=other,
                ).update(is_deleted=True, deleted_at=timezone.now())
                fixed += 1
                self.stdout.write(self.style.WARNING(
                    f"    软删除 {t.real_name or t.username}（#{t.id}）另一学科 ClassTeacher {deleted} 条"
                ))

        self.stdout.write(self.style.SUCCESS(f"回填完成：写入 {len(plans)} 人，跨学科修复 {fixed} 人"))
