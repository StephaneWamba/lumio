"""Media models: video storage, transcoding, HLS streams"""

from django.db import models
from django.contrib.postgres.fields import ArrayField
from apps.courses.models import Lesson


class VideoFile(models.Model):
    """Raw uploaded video file metadata"""

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
    ]

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name="video_file",
    )

    # Raw upload
    s3_key_raw = models.CharField(
        max_length=500,
        help_text="S3 key for raw uploaded video",
    )
    file_size_bytes = models.BigIntegerField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)

    # Processing status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    celery_task_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="Celery task ID for FFmpeg transcoding",
    )
    error_message = models.TextField(blank=True, null=True)

    # Transcoding output
    s3_key_hls_manifest = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 key for HLS master.m3u8",
    )
    hls_variants = ArrayField(
        models.CharField(max_length=500),
        default=list,
        blank=True,
        help_text="List of HLS variant m3u8 keys (480p, 720p, 1080p, etc.)",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Video File"
        verbose_name_plural = "Video Files"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["lesson"]),
        ]

    def __str__(self):
        return f"Video for {self.lesson.title}"


class CloudFrontSignedUrl(models.Model):
    """Cache signed CloudFront URLs for video access"""

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name="cloudfront_signed_url",
    )

    # Signed URL (valid for 24 hours typically)
    signed_url = models.URLField(max_length=2000)
    expires_at = models.DateTimeField(db_index=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "CloudFront Signed URL"
        verbose_name_plural = "CloudFront Signed URLs"
        indexes = [
            models.Index(fields=["lesson"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"Signed URL for {self.lesson.title}"
