"""Celery tasks for analytics — periodic cache refresh."""

import structlog
from celery import shared_task
from django.core.cache import cache
from django.db.models import Avg, Count, Q

from apps.courses.models import Course
from apps.enrollments.models import Enrollment, LessonProgress
from .models import CourseAnalytics

logger = structlog.get_logger(__name__)


@shared_task(name="analytics.refresh_analytics_cache")
def refresh_analytics_cache():
    """Hourly: recalculate aggregated analytics for all published courses.

    Uses a single aggregate query per course instead of 6 separate ones.
    Invalidates Redis cache after each save so retrieve() shows fresh data.
    """
    courses = Course.objects.filter(is_published=True)
    refreshed = 0

    for course in courses:
        analytics, _ = CourseAnalytics.objects.get_or_create(course=course)

        # Single aggregate query replaces 4 separate count/avg queries
        stats = Enrollment.objects.filter(course=course).aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(progress_percentage__gt=0)),
            completed=Count("id", filter=Q(progress_percentage=100)),
            avg_progress=Avg("progress_percentage"),
        )

        quiz_avg = LessonProgress.objects.filter(
            enrollment__course=course,
            highest_quiz_score__isnull=False,
        ).aggregate(avg=Avg("highest_quiz_score"))["avg"]

        analytics.total_enrollments = stats["total"] or 0
        analytics.active_students = stats["active"] or 0
        analytics.completed_students = stats["completed"] or 0
        analytics.average_progress = stats["avg_progress"] or 0
        if quiz_avg is not None:
            analytics.average_quiz_score = quiz_avg

        analytics.save()

        # Invalidate Redis cache so next retrieve() reflects fresh DB data
        cache.delete(f"analytics:course:{analytics.pk}")
        refreshed += 1

    logger.info("analytics_refresh_complete", refreshed=refreshed)
    return {"refreshed": refreshed}
