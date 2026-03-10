# Generated migration for assessments app
from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0001_initial'),
        ('enrollments', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Quiz',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('passing_score', models.DecimalField(decimal_places=2, default=70, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], help_text='Percentage score required to pass (0-100)')),
                ('time_limit_minutes', models.IntegerField(blank=True, null=True)),
                ('shuffle_questions', models.BooleanField(default=True)),
                ('show_answers_after_submission', models.BooleanField(default=True)),
                ('allow_retake', models.BooleanField(default=True)),
                ('max_attempts', models.IntegerField(blank=True, null=True)),
                ('difficulty', models.CharField(choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')], default='medium', max_length=20)),
                ('adaptive_enabled', models.BooleanField(default=False, help_text='Enable adaptive difficulty based on performance')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lesson', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='quiz', to='courses.lesson')),
            ],
            options={
                'verbose_name': 'Quiz',
                'verbose_name_plural': 'Quizzes',
                'ordering': ['lesson'],
            },
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('question_type', models.CharField(choices=[('multiple_choice', 'Multiple Choice'), ('true_false', 'True/False'), ('short_answer', 'Short Answer'), ('essay', 'Essay')], default='multiple_choice', max_length=50)),
                ('text', models.TextField()),
                ('explanation', models.TextField(blank=True, help_text='Explanation shown after submission')),
                ('points', models.DecimalField(decimal_places=2, default=1, max_digits=5, validators=[django.core.validators.MinValueValidator(0)])),
                ('difficulty', models.CharField(choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')], default='medium', max_length=20)),
                ('order', models.PositiveIntegerField(db_index=True, default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='assessments.quiz')),
            ],
            options={
                'verbose_name': 'Question',
                'verbose_name_plural': 'Questions',
                'ordering': ['quiz', 'order'],
            },
        ),
        migrations.CreateModel(
            name='QuestionOption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField()),
                ('is_correct', models.BooleanField(default=False)),
                ('order', models.PositiveIntegerField(db_index=True, default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='options', to='assessments.question')),
            ],
            options={
                'verbose_name': 'Question Option',
                'verbose_name_plural': 'Question Options',
                'ordering': ['question', 'order'],
            },
        ),
        migrations.CreateModel(
            name='QuizAttempt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('in_progress', 'In Progress'), ('submitted', 'Submitted'), ('graded', 'Graded')], db_index=True, default='in_progress', max_length=20)),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('submitted_at', models.DateTimeField(blank=True, null=True)),
                ('score', models.DecimalField(blank=True, decimal_places=2, help_text='Points earned out of total possible points', max_digits=5, null=True)),
                ('percentage_score', models.DecimalField(blank=True, decimal_places=2, help_text='Percentage score (0-100)', max_digits=5, null=True)),
                ('is_passed', models.BooleanField(blank=True, null=True)),
                ('attempt_number', models.PositiveIntegerField(default=1)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('quiz', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='assessments.quiz')),
                ('lesson_progress', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='quiz_attempts', to='enrollments.lessonprogress')),
            ],
            options={
                'verbose_name': 'Quiz Attempt',
                'verbose_name_plural': 'Quiz Attempts',
                'ordering': ['-started_at'],
            },
        ),
        migrations.CreateModel(
            name='AttemptAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text_answer', models.TextField(blank=True, help_text='For short answer/essay')),
                ('is_correct', models.BooleanField(blank=True, null=True)),
                ('points_earned', models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ('graded_by', models.CharField(blank=True, help_text='Instructor who graded this answer', max_length=255)),
                ('grading_notes', models.TextField(blank=True)),
                ('graded_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('attempt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='answers', to='assessments.quizattempt')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempt_answers', to='assessments.question')),
                ('selected_option', models.ForeignKey(blank=True, help_text='For multiple choice/true-false', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='student_answers', to='assessments.questionoption')),
            ],
            options={
                'verbose_name': 'Attempt Answer',
                'verbose_name_plural': 'Attempt Answers',
            },
        ),
        migrations.AddIndex(
            model_name='question',
            index=models.Index(fields=['quiz', 'order'], name='assessments_qu_a1b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='quizattempt',
            index=models.Index(fields=['lesson_progress', 'quiz'], name='assessments_le_a1b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='quizattempt',
            index=models.Index(fields=['status', 'submitted_at'], name='assessments_st_idx'),
        ),
        migrations.AddIndex(
            model_name='attemptanswer',
            index=models.Index(fields=['attempt', 'is_correct'], name='assessments_at_a1b2c_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='question',
            unique_together={('quiz', 'order')},
        ),
        migrations.AlterUniqueTogether(
            name='questionoption',
            unique_together={('question', 'order')},
        ),
        migrations.AlterUniqueTogether(
            name='quizattempt',
            unique_together={('lesson_progress', 'quiz', 'attempt_number')},
        ),
        migrations.AlterUniqueTogether(
            name='attemptanswer',
            unique_together={('attempt', 'question')},
        ),
    ]
