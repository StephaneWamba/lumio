"""Enrollments app admin configuration"""
from django.contrib import admin
from .models import Enrollment, ProgressEvent, LessonProgress


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    """Admin for enrollments"""

    list_display = ["student", "course", "progress_percentage", "completed_at", "created_at"]
    list_filter = ["course", "completed_at", "created_at"]
    search_fields = ["student__email", "student__name", "course__title"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ProgressEvent)
class ProgressEventAdmin(admin.ModelAdmin):
    """Admin for progress events"""

    list_display = ["student", "course", "event_type", "timestamp"]
    list_filter = ["event_type", "timestamp", "course"]
    search_fields = ["student__email", "course__title", "lesson__title"]
    readonly_fields = ["timestamp"]


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    """Admin for lesson progress"""

    list_display = ["enrollment", "lesson", "completed_at", "quiz_passed", "highest_quiz_score"]
    list_filter = ["completed_at", "quiz_passed", "created_at"]
    search_fields = ["enrollment__student__email", "lesson__title"]
    readonly_fields = ["created_at", "updated_at"]
