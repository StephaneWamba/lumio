"""Notifications app models"""
from django.db import models
from django.contrib.postgres.fields import ArrayField
from apps.users.models import User


class NotificationTemplate(models.Model):
    """Reusable notification templates"""

    TRIGGER_COURSE_PUBLISHED = "course_published"
    TRIGGER_ENROLLMENT_CONFIRMED = "enrollment_confirmed"
    TRIGGER_LESSON_AVAILABLE = "lesson_available"
    TRIGGER_DRIP_CONTENT_RELEASED = "drip_content_released"
    TRIGGER_QUIZ_AVAILABLE = "quiz_available"
    TRIGGER_QUIZ_GRADED = "quiz_graded"
    TRIGGER_CERTIFICATE_EARNED = "certificate_earned"
    TRIGGER_INSTRUCTOR_ANNOUNCEMENT = "instructor_announcement"

    TRIGGER_CHOICES = [
        (TRIGGER_COURSE_PUBLISHED, "Course Published"),
        (TRIGGER_ENROLLMENT_CONFIRMED, "Enrollment Confirmed"),
        (TRIGGER_LESSON_AVAILABLE, "Lesson Available"),
        (TRIGGER_DRIP_CONTENT_RELEASED, "Drip Content Released"),
        (TRIGGER_QUIZ_AVAILABLE, "Quiz Available"),
        (TRIGGER_QUIZ_GRADED, "Quiz Graded"),
        (TRIGGER_CERTIFICATE_EARNED, "Certificate Earned"),
        (TRIGGER_INSTRUCTOR_ANNOUNCEMENT, "Instructor Announcement"),
    ]

    trigger = models.CharField(
        max_length=50,
        choices=TRIGGER_CHOICES,
        unique=True,
    )
    name = models.CharField(max_length=255)
    subject = models.CharField(max_length=255, help_text="Email subject with optional placeholders")
    message = models.TextField(help_text="Notification message with optional placeholders: {user_name}, {course_title}, etc.")

    # Channel preferences
    send_in_app = models.BooleanField(default=True)
    send_email = models.BooleanField(default=True)
    send_push = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"
        ordering = ["trigger"]

    def __str__(self):
        return self.name


class NotificationPreference(models.Model):
    """User notification preferences"""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="notification_preferences",
    )

    # Channel preferences (global)
    enable_in_app = models.BooleanField(default=True)
    enable_email = models.BooleanField(default=True)
    enable_push = models.BooleanField(default=False)

    # Digest preferences
    email_digest_frequency = models.CharField(
        max_length=20,
        choices=[
            ("immediate", "Immediate"),
            ("daily", "Daily"),
            ("weekly", "Weekly"),
            ("never", "Never"),
        ],
        default="daily",
    )

    # Notification categories to receive
    enabled_categories = ArrayField(
        models.CharField(max_length=50),
        default=list,
        help_text="List of trigger types to receive notifications for",
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notification Preference"
        verbose_name_plural = "Notification Preferences"

    def __str__(self):
        return f"{self.user.name} - Notification Preferences"


class Notification(models.Model):
    """User notifications (in-app and tracking)"""

    NOTIFICATION_TYPE_INFO = "info"
    NOTIFICATION_TYPE_SUCCESS = "success"
    NOTIFICATION_TYPE_WARNING = "warning"
    NOTIFICATION_TYPE_ERROR = "error"

    TYPE_CHOICES = [
        (NOTIFICATION_TYPE_INFO, "Info"),
        (NOTIFICATION_TYPE_SUCCESS, "Success"),
        (NOTIFICATION_TYPE_WARNING, "Warning"),
        (NOTIFICATION_TYPE_ERROR, "Error"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    template = models.ForeignKey(
        NotificationTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    notification_type = models.CharField(
        max_length=20,
        choices=TYPE_CHOICES,
        default=NOTIFICATION_TYPE_INFO,
    )
    subject = models.CharField(max_length=255)
    message = models.TextField()

    # Context for notification
    action_url = models.URLField(blank=True, help_text="Link to action related to notification")

    # Delivery status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)

    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(blank=True, null=True)

    push_sent = models.BooleanField(default=False)
    push_sent_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["is_read", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.user.name} - {self.subject}"

    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            from django.utils import timezone
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])


class NotificationLog(models.Model):
    """Audit log for notification delivery"""

    LOG_TYPE_CREATED = "created"
    LOG_TYPE_EMAIL_SENT = "email_sent"
    LOG_TYPE_EMAIL_FAILED = "email_failed"
    LOG_TYPE_PUSH_SENT = "push_sent"
    LOG_TYPE_PUSH_FAILED = "push_failed"
    LOG_TYPE_READ = "read"

    LOG_TYPE_CHOICES = [
        (LOG_TYPE_CREATED, "Created"),
        (LOG_TYPE_EMAIL_SENT, "Email Sent"),
        (LOG_TYPE_EMAIL_FAILED, "Email Failed"),
        (LOG_TYPE_PUSH_SENT, "Push Sent"),
        (LOG_TYPE_PUSH_FAILED, "Push Failed"),
        (LOG_TYPE_READ, "Read"),
    ]

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    log_type = models.CharField(
        max_length=20,
        choices=LOG_TYPE_CHOICES,
    )
    details = models.TextField(blank=True, help_text="JSON details of the log entry")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notification Log"
        verbose_name_plural = "Notification Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["notification", "-created_at"]),
            models.Index(fields=["log_type", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.notification.user.name} - {self.get_log_type_display()}"
