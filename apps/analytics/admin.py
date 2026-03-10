"""Analytics app admin configuration"""
from django.contrib import admin
from .models import (
    CourseAnalytics,
    LessonAnalytics,
    QuizAnalytics,
    StudentProgressSnapshot,
    EngagementMetric,
)


@admin.register(CourseAnalytics)
class CourseAnalyticsAdmin(admin.ModelAdmin):
    """Admin for course analytics"""

    list_display = [
        "course",
        "total_enrollments",
        "completed_students",
        "average_progress",
        "average_quiz_score",
        "quiz_pass_rate",
        "last_updated",
    ]
    list_filter = ["last_updated", "created_at"]
    search_fields = ["course__title"]
    readonly_fields = [
        "total_enrollments",
        "active_students",
        "completed_students",
        "average_progress",
        "median_progress",
        "average_quiz_score",
        "quiz_pass_rate",
        "average_time_spent_minutes",
        "total_views",
        "unique_viewers",
        "last_updated",
        "created_at",
    ]


@admin.register(LessonAnalytics)
class LessonAnalyticsAdmin(admin.ModelAdmin):
    """Admin for lesson analytics"""

    list_display = [
        "lesson",
        "total_views",
        "unique_viewers",
        "completion_rate",
        "last_updated",
    ]
    list_filter = ["last_updated"]
    search_fields = ["lesson__title"]
    readonly_fields = ["last_updated", "created_at"]


@admin.register(QuizAnalytics)
class QuizAnalyticsAdmin(admin.ModelAdmin):
    """Admin for quiz analytics"""

    list_display = [
        "quiz",
        "total_attempts",
        "unique_test_takers",
        "average_score",
        "pass_rate",
        "last_updated",
    ]
    list_filter = ["last_updated"]
    search_fields = ["quiz__title"]
    readonly_fields = ["last_updated", "created_at"]


@admin.register(StudentProgressSnapshot)
class StudentProgressSnapshotAdmin(admin.ModelAdmin):
    """Admin for student progress snapshots"""

    list_display = [
        "enrollment",
        "snapshot_date",
        "progress_percentage",
        "lessons_completed",
        "quizzes_passed",
    ]
    list_filter = ["snapshot_date"]
    search_fields = [
        "enrollment__student__name",
        "enrollment__course__title",
    ]
    readonly_fields = ["created_at"]


@admin.register(EngagementMetric)
class EngagementMetricAdmin(admin.ModelAdmin):
    """Admin for engagement metrics"""

    list_display = [
        "course",
        "student",
        "metric_type",
        "count",
        "last_recorded",
    ]
    list_filter = ["metric_type", "last_recorded"]
    search_fields = [
        "course__title",
        "student__name",
        "student__email",
    ]
    readonly_fields = ["created_at"]
