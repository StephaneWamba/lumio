"""Celery tasks for cohorts — drip unlock scanner."""

import structlog
from celery import shared_task
from django.utils import timezone

from .models import DripSchedule

logger = structlog.get_logger(__name__)


@shared_task(name="cohorts.scan_and_release_drip")
def scan_and_release_drip():
    """Hourly: release all DripSchedules whose scheduled time has passed.

    Idempotent: skips schedules already marked is_released=True.
    Uses bulk update for efficiency.
    """
    now = timezone.now()

    pending = DripSchedule.objects.filter(
        is_active=True,
        is_released=False,
    ).select_related("cohort")

    to_release = [s.pk for s in pending if s.is_ready_to_release]

    if to_release:
        DripSchedule.objects.filter(pk__in=to_release).update(
            is_released=True,
            released_at=now,
        )

    logger.info("drip_scan_complete", released=len(to_release))
    return {"released": len(to_release)}
