from apps.users.models import User
for u in User.objects.filter(username__in=['admin_province','admin_school','teacher01','student01']):
    u.set_password('123456')
    u.save()
    print(u.username, u.check_password('123456'))
quit()
