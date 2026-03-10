# Generated migration for analytics app
from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0001_initial'),
        ('users', '0001_initial'),
        ('assessments', '0001_initial'),
        ('enrollments', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CourseAnalytics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_enrollments', models.IntegerField(default=0)),
                ('active_students', models.IntegerField(default=0, help_text='Students with progress > 0%')),
                ('completed_students', models.IntegerField(default=0)),
                ('average_progress', models.DecimalField(decimal_places=2, default=0, help_text='Average course completion percentage', max_digits=5)),
                ('median_progress', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('average_quiz_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('quiz_pass_rate', models.DecimalField(decimal_places=2, default=0, help_text='Percentage of students who passed quizzes', max_digits=5)),
                ('average_time_spent_minutes', models.IntegerField(default=0)),
                ('total_views', models.IntegerField(default=0)),
                ('unique_viewers', models.IntegerField(default=0)),
                ('total_revenue', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('total_refunded', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('average_rating', models.DecimalField(blank=True, decimal_places=2, help_text='Average course rating from reviews', max_digits=3, null=True)),
                ('total_reviews', models.IntegerField(default=0)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('calculated_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='analytics', to='courses.course')),
            ],
            options={
                'verbose_name': 'Course Analytics',
                'verbose_name_plural': 'Course Analytics',
            },
        ),
        migrations.CreateModel(
            name='LessonAnalytics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_views', models.IntegerField(default=0)),
                ('unique_viewers', models.IntegerField(default=0)),
                ('average_time_spent_seconds', models.IntegerField(default=0)),
                ('completion_count', models.IntegerField(default=0)),
                ('completion_rate', models.DecimalField(decimal_places=2, default=0, help_text='Percentage of viewers who completed', max_digits=5)),
                ('average_drop_off_percent', models.DecimalField(decimal_places=2, default=0, help_text='Average percentage at which users stop watching', max_digits=5)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('calculated_at', models.DateTimeField(auto_now_add=True)),
                ('lesson', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='analytics', to='courses.lesson')),
            ],
            options={
                'verbose_name': 'Lesson Analytics',
                'verbose_name_plural': 'Lesson Analytics',
            },
        ),
        migrations.CreateModel(
            name='QuizAnalytics',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('total_attempts', models.IntegerField(default=0)),
                ('unique_test_takers', models.IntegerField(default=0)),
                ('average_attempts_per_student', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('average_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('median_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('pass_rate', models.DecimalField(decimal_places=2, default=0, help_text='Percentage of attempts that passed', max_digits=5)),
                ('average_time_minutes', models.IntegerField(default=0)),
                ('most_missed_question_id', models.IntegerField(blank=True, null=True)),
                ('question_difficulty_scores', django.contrib.postgres.fields.ArrayField(base_field=models.DecimalField(decimal_places=2, max_digits=5), blank=True, default=list, help_text='Difficulty score for each question (lower = harder)', size=None)),
                ('last_updated', models.DateTimeField(auto_now=True)),
                ('calculated_at', models.DateTimeField(auto_now_add=True)),
                ('quiz', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='analytics', to='assessments.quiz')),
            ],
            options={
                'verbose_name': 'Quiz Analytics',
                'verbose_name_plural': 'Quiz Analytics',
            },
        ),
        migrations.CreateModel(
            name='StudentProgressSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('progress_percentage', models.DecimalField(decimal_places=2, max_digits=5)),
                ('lessons_completed', models.IntegerField()),
                ('quizzes_passed', models.IntegerField()),
                ('total_time_spent_minutes', models.IntegerField()),
                ('average_quiz_score', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('snapshot_date', models.DateField(auto_now_add=True, db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('enrollment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='progress_snapshots', to='enrollments.enrollment')),
            ],
            options={
                'verbose_name': 'Student Progress Snapshot',
                'verbose_name_plural': 'Student Progress Snapshots',
                'ordering': ['-snapshot_date'],
            },
        ),
        migrations.CreateModel(
            name='EngagementMetric',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('metric_type', models.CharField(choices=[('lesson_view', 'Lesson View'), ('quiz_attempt', 'Quiz Attempt'), ('forum_post', 'Forum Post'), ('assignment_submit', 'Assignment Submit'), ('resource_download', 'Resource Download')], max_length=50)),
                ('count', models.IntegerField(default=1)),
                ('last_recorded', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='engagement_metrics', to='courses.course')),
                ('student', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='engagement_metrics', to='users.user')),
            ],
            options={
                'verbose_name': 'Engagement Metric',
                'verbose_name_plural': 'Engagement Metrics',
                'ordering': ['-last_recorded'],
            },
        ),
        migrations.AddIndex(
            model_name='studentprogresssnapshot',
            index=models.Index(fields=['enrollment', '-snapshot_date'], name='analytics_enrollment_snapshot_idx'),
        ),
        migrations.AddIndex(
            model_name='studentprogresssnapshot',
            index=models.Index(fields=['enrollment', 'snapshot_date'], name='analytics_enrollment_date_idx'),
        ),
        migrations.AddIndex(
            model_name='engagementmetric',
            index=models.Index(fields=['course', 'student', 'metric_type'], name='engagement_metric_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='studentprogresssnapshot',
            unique_together={('enrollment', 'snapshot_date')},
        ),
        migrations.AlterUniqueTogether(
            name='engagementmetric',
            unique_together={('course', 'student', 'metric_type')},
        ),
    ]
