"""Cohorts and drip publishing models"""

from django.db import models
from django.utils import timezone
from datetime import timedelta
from apps.users.models import User
from apps.courses.models import Course, Section, Lesson
from apps.enrollments.models import Enrollment


class Cohort(models.Model):
    """Cohort: group of students in a course with synchronized content drip"""

    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="cohorts",
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Cohort timing
    start_date = models.DateTimeField(help_text="When cohort starts and content begins dripping")
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When cohort ends (optional, for session-based courses)",
    )

    # Enrollment control
    max_students = models.IntegerField(
        null=True,
        blank=True,
        help_text="Max students in cohort (null = unlimited)",
    )
    is_open = models.BooleanField(
        default=True,
        help_text="Can new students enroll in this cohort",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cohort"
        verbose_name_plural = "Cohorts"
        unique_together = [("course", "name")]
        indexes = [
            models.Index(fields=["course", "start_date"]),
            models.Index(fields=["is_open"]),
        ]
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.course.title} - {self.name}"

    @property
    def member_count(self):
        """Count active members"""
        return self.members.filter(is_active=True).count()

    @property
    def is_active(self):
        """Check if cohort is currently running"""
        now = timezone.now()
        return self.start_date <= now and (not self.end_date or now <= self.end_date)


class CohortMember(models.Model):
    """Student membership in a cohort"""

    cohort = models.ForeignKey(
        Cohort,
        on_delete=models.CASCADE,
        related_name="members",
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="cohort_memberships",
    )
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="cohort_member",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether student is actively enrolled",
    )

    # Timing
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Cohort Member"
        verbose_name_plural = "Cohort Members"
        unique_together = [("cohort", "student")]
        indexes = [
            models.Index(fields=["cohort", "is_active"]),
            models.Index(fields=["student"]),
        ]

    def __str__(self):
        return f"{self.student.name} → {self.cohort.name}"


class DripSchedule(models.Model):
    """Schedule for releasing lesson/section content to a cohort"""

    DRIP_TYPE_LESSON = "lesson"
    DRIP_TYPE_SECTION = "section"

    DRIP_TYPES = [
        (DRIP_TYPE_LESSON, "Lesson"),
        (DRIP_TYPE_SECTION, "Section"),
    ]

    cohort = models.ForeignKey(
        Cohort,
        on_delete=models.CASCADE,
        related_name="drip_schedules",
    )

    # Content to drip
    drip_type = models.CharField(
        max_length=50,
        choices=DRIP_TYPES,
        default=DRIP_TYPE_LESSON,
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="drip_schedules",
        help_text="Lesson to release (if drip_type=lesson)",
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="drip_schedules",
        help_text="Section to release (if drip_type=section)",
    )

    # Timing
    days_after_start = models.IntegerField(
        default=0,
        help_text="Days after cohort start date to release content",
    )
    release_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Absolute time to release (overrides days_after_start if set)",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this drip schedule is active",
    )
    is_released = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether content has been released to cohort members",
    )
    released_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When content was actually released",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Drip Schedule"
        verbose_name_plural = "Drip Schedules"
        indexes = [
            models.Index(fields=["cohort", "release_at"]),
            models.Index(fields=["is_released", "release_at"]),
        ]
        ordering = ["cohort", "release_at"]

    def __str__(self):
        content = self.lesson or self.section
        return f"{self.cohort.name} - {content} (Day {self.days_after_start})"

    @property
    def scheduled_release_time(self):
        """Get the calculated release time"""
        if self.release_at:
            return self.release_at
        return self.cohort.start_date + timedelta(days=self.days_after_start)

    @property
    def is_ready_to_release(self):
        """Check if content should be released now"""
        if not self.is_active or self.is_released:
            return False
        return timezone.now() >= self.scheduled_release_time
