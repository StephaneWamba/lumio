# Generated migration for media app
from django.db import migrations, models
import django.db.models.deletion
import django.contrib.postgres.fields


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('courses', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='VideoFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('s3_key_raw', models.CharField(help_text='S3 key for raw uploaded video', max_length=500)),
                ('file_size_bytes', models.BigIntegerField(blank=True, null=True)),
                ('duration_seconds', models.IntegerField(blank=True, null=True)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')], db_index=True, default='pending', max_length=20)),
                ('celery_task_id', models.CharField(blank=True, help_text='Celery task ID for FFmpeg transcoding', max_length=255, null=True)),
                ('error_message', models.TextField(blank=True, null=True)),
                ('s3_key_hls_manifest', models.CharField(blank=True, help_text='S3 key for HLS master.m3u8', max_length=500, null=True)),
                ('hls_variants', django.contrib.postgres.fields.ArrayField(base_field=models.CharField(max_length=500), blank=True, default=list, help_text='List of HLS variant m3u8 keys (480p, 720p, 1080p, etc.)')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lesson', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='video_file', to='courses.lesson')),
            ],
            options={
                'verbose_name': 'Video File',
                'verbose_name_plural': 'Video Files',
            },
        ),
        migrations.CreateModel(
            name='CloudFrontSignedUrl',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('signed_url', models.URLField(max_length=2000)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('lesson', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='cloudfront_signed_url', to='courses.lesson')),
            ],
            options={
                'verbose_name': 'CloudFront Signed URL',
                'verbose_name_plural': 'CloudFront Signed URLs',
            },
        ),
        migrations.AddIndex(
            model_name='videofile',
            index=models.Index(fields=['status', 'created_at'], name='media_vi_status_a1b2c_idx'),
        ),
        migrations.AddIndex(
            model_name='videofile',
            index=models.Index(fields=['lesson'], name='media_vi_lesson_idx'),
        ),
        migrations.AddIndex(
            model_name='cloudfrontsignedurl',
            index=models.Index(fields=['lesson'], name='media_cl_lesson_idx'),
        ),
        migrations.AddIndex(
            model_name='cloudfrontsignedurl',
            index=models.Index(fields=['expires_at'], name='media_cl_expires_idx'),
        ),
    ]
