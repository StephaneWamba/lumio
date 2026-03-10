# Generated migration for courses app
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.search


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(db_index=True, max_length=255)),
                ('description', models.TextField(blank=True)),
                ('thumbnail_url', models.URLField(blank=True, null=True)),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('duration_minutes', models.IntegerField(blank=True, null=True)),
                ('is_published', models.BooleanField(db_index=True, default=False)),
                ('is_archived', models.BooleanField(default=False)),
                ('search_vector', django.contrib.postgres.search.SearchVectorField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('instructor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='courses', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Course',
                'verbose_name_plural': 'Courses',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255)),
                ('description', models.TextField(blank=True)),
                ('order', models.PositiveIntegerField(db_index=True, default=0)),
                ('is_published', models.BooleanField(db_index=True, default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='courses.course')),
            ],
            options={
                'verbose_name': 'Section',
                'verbose_name_plural': 'Sections',
                'ordering': ['course', 'order'],
                'unique_together': {('course', 'order')},
            },
        ),
        migrations.CreateModel(
            name='Lesson',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(db_index=True, max_length=255)),
                ('description', models.TextField(blank=True)),
                ('content', models.TextField(blank=True, help_text='Markdown content')),
                ('video_s3_key', models.CharField(blank=True, help_text='S3 key for video file (not public URL)', max_length=500, null=True)),
                ('video_duration_seconds', models.IntegerField(blank=True, null=True)),
                ('is_video_processed', models.BooleanField(default=False, help_text='Whether video has been transcoded to HLS')),
                ('order', models.PositiveIntegerField(db_index=True, default=0)),
                ('is_published', models.BooleanField(db_index=True, default=False)),
                ('search_vector', django.contrib.postgres.search.SearchVectorField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('prerequisite_lesson', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='dependent_lessons', to='courses.lesson')),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lessons', to='courses.section')),
            ],
            options={
                'verbose_name': 'Lesson',
                'verbose_name_plural': 'Lessons',
                'ordering': ['section', 'order'],
                'unique_together': {('section', 'order')},
            },
        ),
        migrations.AddIndex(
            model_name='course',
            index=models.Index(fields=['instructor', 'is_published'], name='courses_co_instru_idx'),
        ),
        migrations.AddIndex(
            model_name='course',
            index=models.Index(fields=['is_published', '-created_at'], name='courses_co_is_publ_idx'),
        ),
        migrations.AddIndex(
            model_name='section',
            index=models.Index(fields=['course', 'order'], name='courses_se_course__idx'),
        ),
        migrations.AddIndex(
            model_name='section',
            index=models.Index(fields=['course', 'is_published'], name='courses_se_course__idx_2'),
        ),
        migrations.AddIndex(
            model_name='lesson',
            index=models.Index(fields=['section', 'order'], name='courses_le_section_idx'),
        ),
        migrations.AddIndex(
            model_name='lesson',
            index=models.Index(fields=['section', 'is_published'], name='courses_le_section_idx_2'),
        ),
        migrations.AddIndex(
            model_name='lesson',
            index=models.Index(fields=['prerequisite_lesson'], name='courses_le_prereq__idx'),
        ),
    ]
