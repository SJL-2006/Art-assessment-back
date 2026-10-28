from django.core.management.base import BaseCommand

from apps.exam import services


class Command(BaseCommand):
    """定时自动提交已到结束时间仍未提交的答卷。

    用法：python manage.py auto_submit_exams
    建议配合系统计划任务（Linux cron / Windows 任务计划）周期性执行，
    例如每分钟执行一次，保证限时测评到期后答卷及时自动提交。
    """

    help = "自动提交已到结束时间仍未提交的答卷"

    def handle(self, *args, **options):
        count = services.auto_submit_overdue_sheets()
        self.stdout.write(self.style.SUCCESS(f"已自动提交 {count} 份答卷"))
