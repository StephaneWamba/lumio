"""Analytics app serializers"""

from rest_framework import serializers
from .models import (
    CourseAnalytics,
    LessonAnalytics,
    QuizAnalytics,
    StudentProgressSnapshot,
    EngagementMetric,
)
from apps.courses.serializers import CourseListSerializer


class CourseAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for course analytics"""

    course = CourseListSerializer(read_only=True)

    class Meta:
        model = CourseAnalytics
        fields = [
            "id",
            "course",
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
            "total_revenue",
            "total_refunded",
            "average_rating",
            "total_reviews",
            "last_updated",
        ]
        read_only_fields = fields


class LessonAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for lesson analytics"""

    lesson_title = serializers.CharField(
        source="lesson.title",
        read_only=True,
    )

    class Meta:
        model = LessonAnalytics
        fields = [
            "id",
            "lesson_title",
            "total_views",
            "unique_viewers",
            "average_time_spent_seconds",
            "completion_count",
            "completion_rate",
            "average_drop_off_percent",
            "last_updated",
        ]
        read_only_fields = fields


class QuizAnalyticsSerializer(serializers.ModelSerializer):
    """Serializer for quiz analytics"""

    quiz_title = serializers.CharField(
        source="quiz.title",
        read_only=True,
    )

    class Meta:
        model = QuizAnalytics
        fields = [
            "id",
            "quiz_title",
            "total_attempts",
            "unique_test_takers",
            "average_attempts_per_student",
            "average_score",
            "median_score",
            "pass_rate",
            "average_time_minutes",
            "question_difficulty_scores",
            "last_updated",
        ]
        read_only_fields = fields


class StudentProgressSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for student progress snapshots"""

    student_name = serializers.CharField(
        source="enrollment.student.name",
        read_only=True,
    )
    student_email = serializers.CharField(
        source="enrollment.student.email",
        read_only=True,
    )

    class Meta:
        model = StudentProgressSnapshot
        fields = [
            "id",
            "student_name",
            "student_email",
            "progress_percentage",
            "lessons_completed",
            "quizzes_passed",
            "total_time_spent_minutes",
            "average_quiz_score",
            "snapshot_date",
        ]
        read_only_fields = fields


class EngagementMetricSerializer(serializers.ModelSerializer):
    """Serializer for engagement metrics"""

    course_title = serializers.CharField(
        source="course.title",
        read_only=True,
    )
    student_name = serializers.CharField(
        source="student.name",
        read_only=True,
    )
    metric_type_display = serializers.CharField(
        source="get_metric_type_display",
        read_only=True,
    )

    class Meta:
        model = EngagementMetric
        fields = [
            "id",
            "course_title",
            "student_name",
            "metric_type",
            "metric_type_display",
            "count",
            "last_recorded",
        ]
        read_only_fields = fields
