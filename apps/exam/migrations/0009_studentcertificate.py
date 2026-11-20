from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('exam', '0008_fun_content'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='UploadedCertificate',
            new_name='StudentCertificate',
        ),
        migrations.AlterModelTable(
            name='studentcertificate',
            table='exam_student_certificate',
        ),
        migrations.AlterModelOptions(
            name='studentcertificate',
            options={
                'verbose_name': '学生证书',
                'verbose_name_plural': '学生证书',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AlterField(
            model_name='studentcertificate',
            name='student',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='student_certificates',
                to=settings.AUTH_USER_MODEL,
                verbose_name='学生',
            ),
        ),
    ]
