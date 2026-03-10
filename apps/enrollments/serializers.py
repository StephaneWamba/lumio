"""Enrollments serializers"""

from rest_framework import serializers
from apps.users.serializers import UserSerializer
from apps.courses.serializers import CourseListSerializer
from .models import Enrollment, ProgressEvent, LessonProgress


class EnrollmentSerializer(serializers.ModelSerializer):
    """Enrollment with student and course info"""

    student = UserSerializer(read_only=True)
    course = CourseListSerializer(read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id",
            "student",
            "course",
            "progress_percentage",
            "last_accessed_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["student", "course", "created_at", "updated_at"]


class EnrollCourseSerializer(serializers.Serializer):
    """Request to enroll in a course"""

    course_id = serializers.IntegerField()


class ProgressEventSerializer(serializers.ModelSerializer):
    """Progress event in audit trail"""

    class Meta:
        model = ProgressEvent
        fields = [
            "id",
            "student",
            "course",
            "lesson",
            "event_type",
            "metadata",
            "timestamp",
        ]
        read_only_fields = ["id", "timestamp"]


class LessonProgressSerializer(serializers.ModelSerializer):
    """Lesson completion progress"""

    lesson_title = serializers.CharField(source="lesson.title", read_only=True)

    class Meta:
        model = LessonProgress
        fields = [
            "id",
            "lesson",
            "lesson_title",
            "viewed_at",
            "completed_at",
            "time_spent_seconds",
            "quiz_attempts",
            "quiz_passed",
            "quiz_passed_at",
            "highest_quiz_score",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "viewed_at",
            "completed_at",
            "quiz_passed_at",
            "created_at",
            "updated_at",
        ]
