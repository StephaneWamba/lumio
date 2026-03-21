"""Enrollment signals — fire Celery tasks on enrollment creation."""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Enrollment


@receiver(post_save, sender=Enrollment)
def on_enrollment_created(sender, instance, created, **kwargs):
    """Send welcome email when a new enrollment is created."""
    if not created:
        return

    from apps.notifications.tasks import send_enrollment_welcome

    # Defer until after the DB transaction commits so the Celery worker
    # can safely fetch the Enrollment row.
    transaction.on_commit(lambda: send_enrollment_welcome.delay(instance.id))
