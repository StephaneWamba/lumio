"""Celery tasks for notifications — re-engagement scanner and drip emails."""

import structlog
from celery import shared_task
from datetime import timedelta
from django.utils import timezone

from apps.enrollments.models import Enrollment
from apps.core.email import send_transactional_email
from .models import Notification, NotificationLog

logger = structlog.get_logger(__name__)


@shared_task(name="notifications.scan_reengagement")
def scan_reengagement():
    """Daily: notify and email students inactive for > 7 days on incomplete courses.

    Idempotent: processes all matching enrollments each run.
    Creates an in-app Notification and sends a Resend email.
    """
    cutoff = timezone.now() - timedelta(days=7)

    inactive = Enrollment.objects.filter(
        last_accessed_at__isnull=False,
        last_accessed_at__lt=cutoff,
        progress_percentage__lt=100,
    ).select_related("student", "course")

    notified = 0
    for enrollment in inactive:
        notification = Notification.objects.create(
            user=enrollment.student,
            subject=f"Continue your learning in {enrollment.course.title}",
            message=(
                f"You haven't visited '{enrollment.course.title}' in a while. "
                f"Pick up where you left off!"
            ),
            notification_type=Notification.NOTIFICATION_TYPE_INFO,
        )

        try:
            email_id = send_transactional_email(
                to=enrollment.student.email,
                subject=f"Continue your learning: {enrollment.course.title}",
                html=f"""
<p>Hi {enrollment.student.name},</p>
<p>
  You haven't visited <strong>{enrollment.course.title}</strong> in over a week.
  You're {int(enrollment.progress_percentage)}% of the way through — don't stop now!
</p>
<p>
  <a href="https://lumio.io/learn">Pick up where you left off →</a>
</p>
<p>Keep going,<br>The Lumio Team</p>
""",
            )
            notification.email_sent = True
            notification.email_sent_at = timezone.now()
            notification.save(update_fields=["email_sent", "email_sent_at"])

            NotificationLog.objects.create(
                notification=notification,
                log_type=NotificationLog.LOG_TYPE_EMAIL_SENT,
                details=f'{{"resend_id": "{email_id}"}}',
            )
        except Exception as exc:
            NotificationLog.objects.create(
                notification=notification,
                log_type=NotificationLog.LOG_TYPE_EMAIL_FAILED,
                details=str(exc),
            )
            logger.warning(
                "reengagement_email_failed",
                user_id=enrollment.student.id,
                error=str(exc),
            )

        notified += 1
        logger.info(
            "reengagement_notification_created",
            user_id=enrollment.student.id,
            course_id=enrollment.course.id,
        )

    return {"notified": notified}


@shared_task(name="notifications.send_enrollment_welcome")
def send_enrollment_welcome(enrollment_id: int) -> None:
    """Send a welcome email when a student enrolls in a course.

    Called via .delay() from the Enrollment post_save signal.
    Idempotent: safe to retry — only sends if no prior welcome notification exists.
    """
    try:
        enrollment = Enrollment.objects.select_related("student", "course").get(
            id=enrollment_id
        )
    except Enrollment.DoesNotExist:
        logger.warning("enrollment_welcome_enrollment_not_found", enrollment_id=enrollment_id)
        return {"sent": False}

    # Idempotency check — don't send twice
    already_sent = Notification.objects.filter(
        user=enrollment.student,
        subject__startswith="Welcome to",
        message__contains=enrollment.course.title,
    ).exists()
    if already_sent:
        return {"sent": False, "reason": "already_sent"}

    notification = Notification.objects.create(
        user=enrollment.student,
        subject=f"Welcome to {enrollment.course.title}!",
        message=(
            f"You've successfully enrolled in {enrollment.course.title}. "
            f"Start learning at your own pace!"
        ),
        notification_type=Notification.NOTIFICATION_TYPE_SUCCESS,
    )

    try:
        email_id = send_transactional_email(
            to=enrollment.student.email,
            subject=f"Welcome to {enrollment.course.title}!",
            html=f"""
<p>Hi {enrollment.student.name},</p>
<p>
  You've successfully enrolled in <strong>{enrollment.course.title}</strong>.
  We're excited to have you on board!
</p>
<p>
  <a href="https://lumio.io/learn">Start learning now →</a>
</p>
<p>Happy learning,<br>The Lumio Team</p>
""",
        )
        notification.email_sent = True
        notification.email_sent_at = timezone.now()
        notification.save(update_fields=["email_sent", "email_sent_at"])

        NotificationLog.objects.create(
            notification=notification,
            log_type=NotificationLog.LOG_TYPE_EMAIL_SENT,
            details=f'{{"resend_id": "{email_id}"}}',
        )

        logger.info(
            "enrollment_welcome_sent",
            enrollment_id=enrollment_id,
            user_id=enrollment.student.id,
            course_id=enrollment.course.id,
            email_id=email_id,
        )
        return {"sent": True, "email_id": email_id}

    except Exception as exc:
        NotificationLog.objects.create(
            notification=notification,
            log_type=NotificationLog.LOG_TYPE_EMAIL_FAILED,
            details=str(exc),
        )
        logger.error(
            "enrollment_welcome_email_failed",
            enrollment_id=enrollment_id,
            error=str(exc),
        )
        return {"sent": False, "reason": str(exc)}
