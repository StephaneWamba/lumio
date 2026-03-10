"""Course content models: courses, sections, lessons"""

from django.db import models
from django.contrib.postgres.search import SearchVectorField
from apps.users.models import User


class Course(models.Model):
    """Course model"""

    instructor = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="courses",
        limit_choices_to={"role": User.ROLE_INSTRUCTOR},
    )
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    thumbnail_url = models.URLField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    duration_minutes = models.IntegerField(null=True, blank=True)
    is_published = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False)

    # Full-text search
    search_vector = SearchVectorField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["instructor", "is_published"]),
            models.Index(fields=["is_published", "-created_at"]),
        ]
        verbose_name = "Course"
        verbose_name_plural = "Courses"

    def __str__(self):
        return self.title


class Section(models.Model):
    """Course section model"""

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course", "order"]
        unique_together = ["course", "order"]
        indexes = [
            models.Index(fields=["course", "order"]),
            models.Index(fields=["course", "is_published"]),
        ]
        verbose_name = "Section"
        verbose_name_plural = "Sections"

    def __str__(self):
        return f"{self.course.title} - {self.title}"


class Lesson(models.Model):
    """Individual lesson model"""

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    title = models.CharField(max_length=255, db_index=True)
    description = models.TextField(blank=True)
    content = models.TextField(blank=True, help_text="Markdown content")

    # Video handling (S3 key, never URL - students get signed URLs via endpoint)
    video_s3_key = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 key for video file (not public URL)",
    )
    video_duration_seconds = models.IntegerField(null=True, blank=True)
    is_video_processed = models.BooleanField(
        default=False,
        help_text="Whether video has been transcoded to HLS",
    )

    # Lesson progression
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)
    prerequisite_lesson = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dependent_lessons",
    )

    # Full-text search
    search_vector = SearchVectorField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["section", "order"]
        unique_together = ["section", "order"]
        indexes = [
            models.Index(fields=["section", "order"]),
            models.Index(fields=["section", "is_published"]),
            models.Index(fields=["prerequisite_lesson"]),
        ]
        verbose_name = "Lesson"
        verbose_name_plural = "Lessons"

    def __str__(self):
        return f"{self.section.course.title} - {self.section.title} - {self.title}"
