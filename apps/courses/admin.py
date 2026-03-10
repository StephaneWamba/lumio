"""Courses admin"""

from django.contrib import admin
from .models import Course, Section, Lesson


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    """Course admin"""

    list_display = [
        "title",
        "instructor",
        "price",
        "is_published",
        "created_at",
    ]
    list_filter = [
        "is_published",
        "is_archived",
        "created_at",
    ]
    search_fields = [
        "title",
        "description",
        "instructor__email",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Basic",
            {
                "fields": ("title", "description", "instructor"),
            },
        ),
        (
            "Pricing & Media",
            {
                "fields": ("price", "thumbnail_url", "duration_minutes"),
            },
        ),
        (
            "Status",
            {
                "fields": ("is_published", "is_archived"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    """Section admin"""

    list_display = [
        "title",
        "course",
        "order",
        "is_published",
    ]
    list_filter = [
        "is_published",
        "course",
    ]
    search_fields = [
        "title",
        "course__title",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Basic",
            {
                "fields": ("course", "title", "description", "order"),
            },
        ),
        (
            "Status",
            {
                "fields": ("is_published",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    """Lesson admin"""

    list_display = [
        "title",
        "section",
        "order",
        "is_published",
        "is_video_processed",
    ]
    list_filter = [
        "is_published",
        "is_video_processed",
        "section__course",
    ]
    search_fields = [
        "title",
        "section__title",
        "section__course__title",
    ]
    readonly_fields = [
        "is_video_processed",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        (
            "Basic",
            {
                "fields": ("section", "title", "description", "content", "order"),
            },
        ),
        (
            "Video",
            {
                "fields": (
                    "video_s3_key",
                    "video_duration_seconds",
                    "is_video_processed",
                ),
            },
        ),
        (
            "Progression",
            {
                "fields": ("is_published", "prerequisite_lesson"),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
            },
        ),
    )
