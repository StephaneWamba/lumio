"""Celery tasks for cohorts — drip unlock scanner."""

import structlog
from celery import shared_task
from django.utils import timezone

from .models import DripSchedule
from .unlock import create_lesson_unlocks_for_schedule

logger = structlog.get_logger(__name__)


@shared_task(name="cohorts.scan_and_release_drip")
def scan_and_release_drip():
    """Hourly: release all DripSchedules whose scheduled time has passed.

    Idempotent: skips schedules already marked is_released=True.
    Bulk-creates LessonUnlock records for all active cohort members.
    """
    now = timezone.now()

    pending = DripSchedule.objects.filter(
        is_active=True,
        is_released=False,
    ).select_related("cohort")

    to_release = [s for s in pending if s.is_ready_to_release]
    pks = [s.pk for s in to_release]

    if pks:
        DripSchedule.objects.filter(pk__in=pks).update(
            is_released=True,
            released_at=now,
        )

    unlocks_created = 0
    for schedule in to_release:
        schedule.is_released = True
        schedule.released_at = now
        unlocks_created += create_lesson_unlocks_for_schedule(schedule)

    logger.info("drip_scan_complete", released=len(to_release), unlocks_created=unlocks_created)
    return {"released": len(to_release), "unlocks_created": unlocks_created}
