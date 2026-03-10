"""Analytics app models"""

from django.db import models
from django.contrib.postgres.fields import ArrayField
from apps.courses.models import Course, Section, Lesson
from apps.users.models import User
from apps.enrollments.models import Enrollment
from apps.assessments.models import Quiz


class CourseAnalytics(models.Model):
    """Aggregated analytics for courses"""

    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name="analytics",
    )

    # Enrollment stats
    total_enrollments = models.IntegerField(default=0)
    active_students = models.IntegerField(default=0, help_text="Students with progress > 0%")
    completed_students = models.IntegerField(default=0)

    # Progress stats
    average_progress = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Average course completion percentage",
    )
    median_progress = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    # Performance stats
    average_quiz_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    quiz_pass_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Percentage of students who passed quizzes",
    )

    # Engagement stats
    average_time_spent_minutes = models.IntegerField(default=0)
    total_views = models.IntegerField(default=0)
    unique_viewers = models.IntegerField(default=0)

    # Revenue stats (if applicable)
    total_revenue = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    total_refunded = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    # Rating stats
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Average course rating from reviews",
    )
    total_reviews = models.IntegerField(default=0)

    # Last updated
    last_updated = models.DateTimeField(auto_now=True)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Course Analytics"
        verbose_name_plural = "Course Analytics"

    def __str__(self):
        return f"Analytics for {self.course.title}"


class LessonAnalytics(models.Model):
    """Aggregated analytics for lessons"""

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name="analytics",
    )

    # View stats
    total_views = models.IntegerField(default=0)
    unique_viewers = models.IntegerField(default=0)
    average_time_spent_seconds = models.IntegerField(default=0)

    # Completion stats
    completion_count = models.IntegerField(default=0)
    completion_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Percentage of viewers who completed",
    )

    # Drop-off point (if applicable)
    average_drop_off_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Average percentage at which users stop watching",
    )

    last_updated = models.DateTimeField(auto_now=True)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lesson Analytics"
        verbose_name_plural = "Lesson Analytics"

    def __str__(self):
        return f"Analytics for {self.lesson.title}"


class QuizAnalytics(models.Model):
    """Aggregated analytics for quizzes"""

    quiz = models.OneToOneField(
        Quiz,
        on_delete=models.CASCADE,
        related_name="analytics",
    )

    # Attempt stats
    total_attempts = models.IntegerField(default=0)
    unique_test_takers = models.IntegerField(default=0)
    average_attempts_per_student = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    # Performance stats
    average_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    median_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )
    pass_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Percentage of attempts that passed",
    )

    # Difficulty analysis
    average_time_minutes = models.IntegerField(default=0)
    most_missed_question_id = models.IntegerField(blank=True, null=True)
    question_difficulty_scores = ArrayField(
        models.DecimalField(max_digits=5, decimal_places=2),
        default=list,
        blank=True,
        help_text="Difficulty score for each question (lower = harder)",
    )

    last_updated = models.DateTimeField(auto_now=True)
    calculated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Quiz Analytics"
        verbose_name_plural = "Quiz Analytics"

    def __str__(self):
        return f"Analytics for {self.quiz.title}"


class StudentProgressSnapshot(models.Model):
    """Point-in-time snapshot of student progress for historical tracking"""

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="progress_snapshots",
    )

    # Progress snapshot
    progress_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
    )
    lessons_completed = models.IntegerField()
    quizzes_passed = models.IntegerField()
    total_time_spent_minutes = models.IntegerField()

    # Quiz performance snapshot
    average_quiz_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )

    # Snapshot metadata
    snapshot_date = models.DateField(auto_now_add=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Student Progress Snapshot"
        verbose_name_plural = "Student Progress Snapshots"
        ordering = ["-snapshot_date"]
        indexes = [
            models.Index(fields=["enrollment", "-snapshot_date"]),
        ]
        unique_together = [["enrollment", "snapshot_date"]]

    def __str__(self):
        return f"{self.enrollment.student.name} - {self.snapshot_date}"


class EngagementMetric(models.Model):
    """Engagement metrics for instructors"""

    METRIC_TYPE_LESSON_VIEW = "lesson_view"
    METRIC_TYPE_QUIZ_ATTEMPT = "quiz_attempt"
    METRIC_TYPE_FORUM_POST = "forum_post"
    METRIC_TYPE_ASSIGNMENT_SUBMIT = "assignment_submit"
    METRIC_TYPE_RESOURCE_DOWNLOAD = "resource_download"

    METRIC_TYPE_CHOICES = [
        (METRIC_TYPE_LESSON_VIEW, "Lesson View"),
        (METRIC_TYPE_QUIZ_ATTEMPT, "Quiz Attempt"),
        (METRIC_TYPE_FORUM_POST, "Forum Post"),
        (METRIC_TYPE_ASSIGNMENT_SUBMIT, "Assignment Submit"),
        (METRIC_TYPE_RESOURCE_DOWNLOAD, "Resource Download"),
    ]

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="engagement_metrics",
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="engagement_metrics",
    )

    metric_type = models.CharField(
        max_length=50,
        choices=METRIC_TYPE_CHOICES,
    )
    count = models.IntegerField(default=1)
    last_recorded = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Engagement Metric"
        verbose_name_plural = "Engagement Metrics"
        ordering = ["-last_recorded"]
        indexes = [
            models.Index(fields=["course", "student", "metric_type"]),
        ]
        unique_together = [["course", "student", "metric_type"]]

    def __str__(self):
        return f"{self.student.name} - {self.get_metric_type_display()}"
