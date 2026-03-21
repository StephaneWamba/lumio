from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0001_initial'),
        ('enrollments', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='enrollment',
            name='student',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='enrollments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='enrollment',
            name='course',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='enrollments',
                to='courses.course',
            ),
        ),
        migrations.AlterField(
            model_name='progressevent',
            name='student',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='progress_events',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='progressevent',
            name='course',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='progress_events',
                to='courses.course',
            ),
        ),
        migrations.AlterField(
            model_name='lessonprogress',
            name='enrollment',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='lesson_progress',
                to='enrollments.enrollment',
            ),
        ),
    ]
