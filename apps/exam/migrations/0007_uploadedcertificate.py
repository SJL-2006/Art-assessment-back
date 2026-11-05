from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('exam', '0006_extracurricularupload_deleted_at_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='UploadedCertificate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('is_deleted', models.BooleanField(default=False, verbose_name='是否删除')),
                ('deleted_at', models.DateTimeField(blank=True, null=True, verbose_name='删除时间')),
                ('title', models.CharField(max_length=128, verbose_name='证书标题')),
                ('cert_type', models.CharField(choices=[('exam', '考试证书'), ('competition', '竞赛证书'), ('graduation', '毕业证书'), ('other', '其他')], default='other', max_length=16, verbose_name='证书类型')),
                ('subject', models.CharField(choices=[('art', '美术'), ('music', '音乐'), ('comprehensive', '综合'), ('other', '其他')], default='other', max_length=16, verbose_name='学科')),
                ('issuer', models.CharField(blank=True, default='', max_length=128, verbose_name='颁发机构')),
                ('obtained_at', models.DateField(blank=True, null=True, verbose_name='获得日期')),
                ('image', models.ImageField(upload_to='cert-uploads/%Y/%m/', verbose_name='证书图片')),
                ('note', models.TextField(blank=True, default='', verbose_name='备注')),
                ('status', models.CharField(choices=[('pending', '待审核'), ('approved', '已通过'), ('rejected', '已驳回')], default='pending', max_length=16, verbose_name='审核状态')),
                ('review_comment', models.TextField(blank=True, default='', verbose_name='审核意见')),
                ('reviewed_at', models.DateTimeField(blank=True, null=True, verbose_name='审核时间')),
                ('reviewer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_certificates', to=settings.AUTH_USER_MODEL, verbose_name='审核人')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='uploaded_certificates', to=settings.AUTH_USER_MODEL, verbose_name='上传学生')),
            ],
            options={
                'verbose_name': '学生上传证书',
                'verbose_name_plural': '学生上传证书',
                'db_table': 'exam_uploaded_certificate',
                'ordering': ['-created_at'],
            },
        ),
    ]
