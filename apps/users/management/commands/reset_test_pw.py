from django.core.management.base import BaseCommand

from apps.users.models import User


class Command(BaseCommand):
    help = "重置所有测试用户密码为 123456"

    def handle(self, *args, **options):
        for u in User.objects.filter(username__in=["admin_province", "admin_school", "teacher01", "student01"]):
            u.set_password("123456")
            u.save()
            ok = u.check_password("123456")
            self.stdout.write(self.style.SUCCESS(f"{u.username}: role={u.role}, pw_ok={ok}"))
