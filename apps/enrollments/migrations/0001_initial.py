# Generated migration for enrollments app
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Enrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('progress_percentage', models.DecimalField(decimal_places=2, default=0, help_text='Overall course completion percentage (0-100)', max_digits=5)),
                ('last_accessed_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='courses.course')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Enrollment',
                'verbose_name_plural': 'Enrollments',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ProgressEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event_type', models.CharField(choices=[('lesson_viewed', 'Lesson Viewed'), ('lesson_completed', 'Lesson Completed'), ('quiz_started', 'Quiz Started'), ('quiz_submitted', 'Quiz Submitted'), ('quiz_passed', 'Quiz Passed'), ('course_completed', 'Course Completed')], db_index=True, max_length=50)),
                ('metadata', models.JSONField(blank=True, default=dict, help_text='Additional event context (quiz score, time spent, etc.)')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress_events', to='courses.course')),
                ('lesson', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='progress_events', to='courses.lesson')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress_events', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Progress Event',
                'verbose_name_plural': 'Progress Events',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.CreateModel(
            name='LessonProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('viewed_at', models.DateTimeField(blank=True, null=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('time_spent_seconds', models.IntegerField(default=0)),
                ('quiz_attempts', models.IntegerField(default=0)),
                ('quiz_passed', models.BooleanField(default=False)),
                ('quiz_passed_at', models.DateTimeField(blank=True, null=True)),
                ('highest_quiz_score', models.DecimalField(blank=True, decimal_places=2, help_text='Highest quiz score as percentage (0-100)', max_digits=5, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lesson_progress', to='enrollments.enrollment')),
                ('lesson', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='student_progress', to='courses.lesson')),
            ],
            options={
                'verbose_name': 'Lesson Progress',
                'verbose_name_plural': 'Lesson Progress',
            },
        ),
        migrations.AddIndex(
            model_name='enrollment',
            index=models.Index(fields=['student', 'course'], name='enrollment_st_a1b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='enrollment',
            index=models.Index(fields=['course', 'progress_percentage'], name='enrollment_co_idx'),
        ),
        migrations.AddIndex(
            model_name='enrollment',
            index=models.Index(fields=['completed_at'], name='enrollment_co_a1b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='progressevent',
            index=models.Index(fields=['student', 'course', 'timestamp'], name='enrollments_st_a1b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='progressevent',
            index=models.Index(fields=['event_type', 'timestamp'], name='enrollments_ev_idx'),
        ),
        migrations.AddIndex(
            model_name='progressevent',
            index=models.Index(fields=['lesson', 'event_type'], name='enrollments_le_idx'),
        ),
        migrations.AddIndex(
            model_name='lessonprogress',
            index=models.Index(fields=['enrollment', 'completed_at'], name='enrollments_en_idx'),
        ),
        migrations.AddIndex(
            model_name='lessonprogress',
            index=models.Index(fields=['lesson', 'quiz_passed'], name='enrollments_le_a1b2c_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='enrollment',
            unique_together={('student', 'course')},
        ),
        migrations.AlterUniqueTogether(
            name='lessonprogress',
            unique_together={('enrollment', 'lesson')},
        ),
    ]
