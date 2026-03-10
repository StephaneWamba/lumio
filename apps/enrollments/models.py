"""Enrollments and progress tracking models"""

from django.db import models
from django.contrib.postgres.fields import JSONField
from apps.users.models import User
from apps.courses.models import Course, Lesson


class Enrollment(models.Model):
    """Student enrollment in a course"""

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )

    # Progress tracking
    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Overall course completion percentage (0-100)",
    )
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Enrollment"
        verbose_name_plural = "Enrollments"
        unique_together = [("student", "course")]
        indexes = [
            models.Index(fields=["student", "course"]),
            models.Index(fields=["course", "progress_percentage"]),
            models.Index(fields=["completed_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.student.name} → {self.course.title}"


class ProgressEvent(models.Model):
    """Event-sourced progress events (audit trail)"""

    EVENT_LESSON_VIEWED = "lesson_viewed"
    EVENT_LESSON_COMPLETED = "lesson_completed"
    EVENT_QUIZ_STARTED = "quiz_started"
    EVENT_QUIZ_SUBMITTED = "quiz_submitted"
    EVENT_QUIZ_PASSED = "quiz_passed"
    EVENT_COURSE_COMPLETED = "course_completed"

    EVENT_CHOICES = [
        (EVENT_LESSON_VIEWED, "Lesson Viewed"),
        (EVENT_LESSON_COMPLETED, "Lesson Completed"),
        (EVENT_QUIZ_STARTED, "Quiz Started"),
        (EVENT_QUIZ_SUBMITTED, "Quiz Submitted"),
        (EVENT_QUIZ_PASSED, "Quiz Passed"),
        (EVENT_COURSE_COMPLETED, "Course Completed"),
    ]

    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="progress_events",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="progress_events",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="progress_events",
    )

    event_type = models.CharField(
        max_length=50,
        choices=EVENT_CHOICES,
        db_index=True,
    )
    metadata = JSONField(
        default=dict,
        blank=True,
        help_text="Additional event context (quiz score, time spent, etc.)",
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Progress Event"
        verbose_name_plural = "Progress Events"
        indexes = [
            models.Index(fields=["student", "course", "timestamp"]),
            models.Index(fields=["event_type", "timestamp"]),
            models.Index(fields=["lesson", "event_type"]),
        ]
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.student.name} - {self.get_event_type_display()}"


class LessonProgress(models.Model):
    """Aggregated lesson progress for quick querying"""

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="student_progress",
    )

    # Progress tracking
    viewed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    time_spent_seconds = models.IntegerField(default=0)

    # Quiz progress (if lesson has quiz)
    quiz_attempts = models.IntegerField(default=0)
    quiz_passed = models.BooleanField(default=False)
    quiz_passed_at = models.DateTimeField(null=True, blank=True)
    highest_quiz_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Highest quiz score as percentage (0-100)",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lesson Progress"
        verbose_name_plural = "Lesson Progress"
        unique_together = [("enrollment", "lesson")]
        indexes = [
            models.Index(fields=["enrollment", "completed_at"]),
            models.Index(fields=["lesson", "quiz_passed"]),
        ]

    def __str__(self):
        return f"{self.enrollment.student.name} → {self.lesson.title}"
