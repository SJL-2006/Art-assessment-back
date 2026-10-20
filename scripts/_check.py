from apps.users.models import User
for u in User.objects.filter(username__in=['admin_province','admin_school','teacher01','student01']):
    print(f"{u.username}: active={u.is_active}, role={u.role}, pw_ok={u.check_password('123456')}")
