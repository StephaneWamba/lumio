"""Media app admin configuration"""

from django.contrib import admin
from .models import VideoFile, CloudFrontSignedUrl


@admin.register(VideoFile)
class VideoFileAdmin(admin.ModelAdmin):
    """Admin for video files"""

    list_display = ["lesson", "status", "file_size_bytes", "duration_seconds", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["lesson__title"]
    readonly_fields = ["created_at", "updated_at", "celery_task_id"]


@admin.register(CloudFrontSignedUrl)
class CloudFrontSignedUrlAdmin(admin.ModelAdmin):
    """Admin for cached CloudFront signed URLs"""

    list_display = ["lesson", "expires_at", "created_at"]
    list_filter = ["expires_at", "created_at"]
    search_fields = ["lesson__title"]
    readonly_fields = ["created_at", "updated_at"]
