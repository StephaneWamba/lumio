"""Celery tasks for analytics — periodic cache refresh."""

import structlog
from celery import shared_task
from django.db.models import Avg

from apps.courses.models import Course
from apps.enrollments.models import Enrollment, LessonProgress
from .models import CourseAnalytics

logger = structlog.get_logger(__name__)


@shared_task(name="analytics.refresh_analytics_cache")
def refresh_analytics_cache():
    """Hourly: recalculate aggregated analytics for all published courses.

    Uses get_or_create so courses without an existing analytics record
    get one automatically on the first run.
    """
    courses = Course.objects.filter(is_published=True)
    refreshed = 0

    for course in courses:
        analytics, _ = CourseAnalytics.objects.get_or_create(course=course)
        enrollments = Enrollment.objects.filter(course=course)

        analytics.total_enrollments = enrollments.count()
        analytics.active_students = enrollments.filter(progress_percentage__gt=0).count()
        analytics.completed_students = enrollments.filter(progress_percentage=100).count()
        analytics.average_progress = (
            enrollments.aggregate(Avg("progress_percentage"))["progress_percentage__avg"] or 0
        )

        quiz_avg = LessonProgress.objects.filter(
            enrollment__course=course,
            highest_quiz_score__isnull=False,
        ).aggregate(Avg("highest_quiz_score"))["highest_quiz_score__avg"]

        if quiz_avg is not None:
            analytics.average_quiz_score = quiz_avg

        analytics.save()
        refreshed += 1

    logger.info("analytics_refresh_complete", refreshed=refreshed)
    return {"refreshed": refreshed}
