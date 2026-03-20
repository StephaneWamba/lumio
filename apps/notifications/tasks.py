"""Celery tasks for notifications — re-engagement scanner."""

import structlog
from celery import shared_task
from datetime import timedelta
from django.utils import timezone

from apps.enrollments.models import Enrollment
from .models import Notification

logger = structlog.get_logger(__name__)


@shared_task(name="notifications.scan_reengagement")
def scan_reengagement():
    """Daily: create re-engagement notifications for students inactive >7 days.

    Targets students who:
    - Have a recorded last_accessed_at (i.e. have started the course)
    - Have not accessed in more than 7 days
    - Have not completed the course (progress < 100%)
    """
    cutoff = timezone.now() - timedelta(days=7)

    inactive = Enrollment.objects.filter(
        last_accessed_at__isnull=False,
        last_accessed_at__lt=cutoff,
        progress_percentage__lt=100,
    ).select_related("student", "course")

    notified = 0
    for enrollment in inactive:
        Notification.objects.create(
            user=enrollment.student,
            subject=f"Continue your learning in {enrollment.course.title}",
            message=(
                f"You haven't visited '{enrollment.course.title}' in a while. "
                f"Pick up where you left off!"
            ),
            notification_type=Notification.NOTIFICATION_TYPE_INFO,
        )
        notified += 1
        logger.info(
            "reengagement_notification_created",
            user_id=enrollment.student.id,
            course_id=enrollment.course.id,
        )

    return {"notified": notified}
