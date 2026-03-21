"""Certificates app models"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.courses.models import Course
from apps.enrollments.models import Enrollment


class CertificateTemplate(models.Model):
    """Template for certificates with branding and layout"""

    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name="certificate_template",
    )
    title = models.CharField(
        max_length=255, help_text="Certificate title e.g., 'Certificate of Completion'"
    )
    description = models.TextField(blank=True)
    content = models.TextField(
        help_text=(
            "Certificate body text with optional placeholders: "
            "{student_name}, {course_title}, {completion_date}"
        )
    )

    # Branding
    institution_name = models.CharField(max_length=255, blank=True)
    signature_text = models.CharField(max_length=255, blank=True, help_text="Signatory name/title")
    logo_url = models.URLField(blank=True, help_text="URL to institution logo")

    # Styling
    color_primary = models.CharField(
        max_length=7, default="#003366", help_text="Primary brand color (hex)"
    )
    color_accent = models.CharField(max_length=7, default="#0099CC", help_text="Accent color (hex)")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Certificate Template"
        verbose_name_plural = "Certificate Templates"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.course.title} Certificate"


class CertificateAward(models.Model):
    """Criteria for earning a certificate"""

    CONDITION_COURSE_COMPLETED = "course_completed"
    CONDITION_SCORE_MINIMUM = "score_minimum"
    CONDITION_COURSE_COMPLETED_WITH_SCORE = "course_completed_with_score"

    CONDITION_CHOICES = [
        (CONDITION_COURSE_COMPLETED, "Course Completed"),
        (CONDITION_SCORE_MINIMUM, "Minimum Score Required"),
        (CONDITION_COURSE_COMPLETED_WITH_SCORE, "Course Completed with Minimum Score"),
    ]

    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name="certificate_award",
    )
    condition = models.CharField(
        max_length=50,
        choices=CONDITION_CHOICES,
        default=CONDITION_COURSE_COMPLETED,
    )
    minimum_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Minimum percentage score required (0-100)",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Certificate Award Criteria"
        verbose_name_plural = "Certificate Award Criteria"

    def __str__(self):
        return f"{self.course.title} - {self.get_condition_display()}"

    def check_eligibility(self, enrollment):
        """Check if enrollment qualifies for certificate"""
        if not self.is_active:
            return False

        if self.condition == self.CONDITION_COURSE_COMPLETED:
            return enrollment.progress_percentage == 100

        if self.condition == self.CONDITION_SCORE_MINIMUM:
            from apps.enrollments.models import LessonProgress
            from django.db.models import Avg

            avg_score = LessonProgress.objects.filter(
                enrollment=enrollment,
                highest_quiz_score__isnull=False,
            ).aggregate(avg=Avg("highest_quiz_score"))["avg"]
            if avg_score is None:
                return False
            return avg_score >= self.minimum_score

        if self.condition == self.CONDITION_COURSE_COMPLETED_WITH_SCORE:
            if enrollment.progress_percentage != 100:
                return False
            from apps.enrollments.models import LessonProgress
            from django.db.models import Avg

            avg_score = LessonProgress.objects.filter(
                enrollment=enrollment,
                highest_quiz_score__isnull=False,
            ).aggregate(avg=Avg("highest_quiz_score"))["avg"]
            if avg_score is None:
                return False
            return avg_score >= self.minimum_score

        return False


class EarnedCertificate(models.Model):
    """Certificate earned by a student"""

    enrollment = models.OneToOneField(
        Enrollment,
        on_delete=models.PROTECT,
        related_name="earned_certificate",
    )
    template = models.ForeignKey(
        CertificateTemplate,
        on_delete=models.SET_NULL,
        null=True,
        related_name="earned_certificates",
    )
    certificate_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique identifier for certificate verification",
    )
    issued_at = models.DateTimeField(default=timezone.now)

    # Rendered content
    rendered_content = models.TextField(
        help_text="Final certificate content with placeholders filled in"
    )

    # PDF storage
    pdf_s3_key = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="S3 key for the rendered PDF in the assets bucket",
    )

    # Verification
    is_revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(blank=True, null=True)
    revocation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Earned Certificate"
        verbose_name_plural = "Earned Certificates"
        ordering = ["-issued_at"]

    def __str__(self):
        return f"{self.enrollment.student.name} - {self.enrollment.course.title}"
