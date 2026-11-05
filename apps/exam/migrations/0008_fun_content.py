from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('org', '0003_school_is_directly_affiliated'),
        ('classroom', '0004_classroom_deleted_at_classstudent_deleted_at_and_more'),
        ('exam', '0007_uploadedcertificate'),
    ]

    operations = [
        migrations.CreateModel(
            name='FunContent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('title', models.CharField(max_length=128, verbose_name='标题')),
                ('subject', models.CharField(choices=[('art', '美术'), ('music', '音乐'), ('general', '综合')], default='general', max_length=16, verbose_name='学科')),
                ('category', models.CharField(blank=True, default='', max_length=64, verbose_name='分类')),
                ('summary', models.CharField(blank=True, default='', max_length=255, verbose_name='摘要')),
                ('content', models.TextField(blank=True, default='', verbose_name='正文')),
                ('fun_fact', models.TextField(blank=True, default='', verbose_name='趣味小知识')),
                ('emoji', models.CharField(blank=True, default='', max_length=16, verbose_name='表情图标')),
                ('color', models.CharField(blank=True, default='', max_length=16, verbose_name='主题色')),
                ('read_minutes', models.IntegerField(default=3, verbose_name='阅读时长(分钟)')),
                ('status', models.CharField(choices=[('draft', '草稿'), ('published', '已发布')], default='draft', max_length=16, verbose_name='状态')),
                ('published_at', models.DateTimeField(blank=True, null=True, verbose_name='发布时间')),
                ('creator', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_fun_contents', to=settings.AUTH_USER_MODEL, verbose_name='创建人')),
                ('school', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='org.school', verbose_name='目标学校')),
                ('target_class', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='classroom.classroom', verbose_name='目标班级')),
            ],
            options={
                'verbose_name': '趣味课堂内容',
                'verbose_name_plural': '趣味课堂内容',
                'db_table': 'exam_fun_content',
                'ordering': ['-created_at'],
            },
        ),
    ]
