# Generated migration for cohorts app
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0001_initial'),
        ('enrollments', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Cohort',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('start_date', models.DateTimeField(help_text='When cohort starts and content begins dripping')),
                ('end_date', models.DateTimeField(blank=True, help_text='When cohort ends (optional, for session-based courses)', null=True)),
                ('max_students', models.IntegerField(blank=True, help_text='Max students in cohort (null = unlimited)', null=True)),
                ('is_open', models.BooleanField(default=True, help_text='Can new students enroll in this cohort')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cohorts', to='courses.course')),
            ],
            options={
                'verbose_name': 'Cohort',
                'verbose_name_plural': 'Cohorts',
                'ordering': ['-start_date'],
            },
        ),
        migrations.CreateModel(
            name='DripSchedule',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('drip_type', models.CharField(choices=[('lesson', 'Lesson'), ('section', 'Section')], default='lesson', max_length=50)),
                ('days_after_start', models.IntegerField(default=0, help_text='Days after cohort start date to release content')),
                ('release_at', models.DateTimeField(blank=True, help_text='Absolute time to release (overrides days_after_start if set)', null=True)),
                ('is_active', models.BooleanField(default=True, help_text='Whether this drip schedule is active')),
                ('is_released', models.BooleanField(db_index=True, default=False, help_text='Whether content has been released to cohort members')),
                ('released_at', models.DateTimeField(blank=True, help_text='When content was actually released', null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cohort', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='drip_schedules', to='cohorts.cohort')),
                ('lesson', models.ForeignKey(blank=True, help_text='Lesson to release (if drip_type=lesson)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='drip_schedules', to='courses.lesson')),
                ('section', models.ForeignKey(blank=True, help_text='Section to release (if drip_type=section)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='drip_schedules', to='courses.section')),
            ],
            options={
                'verbose_name': 'Drip Schedule',
                'verbose_name_plural': 'Drip Schedules',
                'ordering': ['cohort', 'release_at'],
            },
        ),
        migrations.CreateModel(
            name='CohortMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('is_active', models.BooleanField(default=True, help_text='Whether student is actively enrolled')),
                ('joined_at', models.DateTimeField(auto_now_add=True)),
                ('left_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('cohort', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='members', to='cohorts.cohort')),
                ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cohort_member', to='enrollments.enrollment')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='cohort_memberships', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Cohort Member',
                'verbose_name_plural': 'Cohort Members',
            },
        ),
        migrations.AddIndex(
            model_name='cohort',
            index=models.Index(fields=['course', 'start_date'], name='cohorts_co_st_a1b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='cohort',
            index=models.Index(fields=['is_open'], name='cohorts_is_idx'),
        ),
        migrations.AddIndex(
            model_name='dripschedule',
            index=models.Index(fields=['cohort', 'release_at'], name='cohorts_dr_co_a1b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='dripschedule',
            index=models.Index(fields=['is_released', 'release_at'], name='cohorts_dr_is_idx'),
        ),
        migrations.AddIndex(
            model_name='cohortmember',
            index=models.Index(fields=['cohort', 'is_active'], name='cohorts_cm_co_idx'),
        ),
        migrations.AddIndex(
            model_name='cohortmember',
            index=models.Index(fields=['student'], name='cohorts_cm_st_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='cohort',
            unique_together={('course', 'name')},
        ),
        migrations.AlterUniqueTogether(
            name='cohortmember',
            unique_together={('cohort', 'student')},
        ),
    ]
