"""Tests for analytics Celery tasks — cache refresh."""

from django.test import TestCase

from apps.users.models import User
from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from apps.analytics.models import CourseAnalytics


class RefreshAnalyticsCacheTaskTests(TestCase):

    def setUp(self):
        self.instructor = User.objects.create_user(
            email="instructor@analytics-tasks.com",
            name="Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Analytics Test Course",
            is_published=True,
        )

    def test_creates_analytics_record_if_missing(self):
        """Task creates CourseAnalytics for published course with no existing record."""
        from apps.analytics.tasks import refresh_analytics_cache
        refresh_analytics_cache()

        self.assertTrue(
            CourseAnalytics.objects.filter(course=self.course).exists(),
            "CourseAnalytics should be created for published course",
        )

    def test_updates_enrollment_counts(self):
        """Task recalculates total_enrollments from actual enrollment count."""
        student = User.objects.create_user(
            email="student@analytics-tasks.com",
            name="Student",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        Enrollment.objects.create(student=student, course=self.course)

        from apps.analytics.tasks import refresh_analytics_cache
        refresh_analytics_cache()

        analytics = CourseAnalytics.objects.get(course=self.course)
        self.assertEqual(analytics.total_enrollments, 1)

    def test_returns_refreshed_count(self):
        """Task returns dict with count of courses refreshed."""
        from apps.analytics.tasks import refresh_analytics_cache
        result = refresh_analytics_cache()

        self.assertIsInstance(result, dict)
        self.assertGreaterEqual(result["refreshed"], 1)

    def test_does_not_create_analytics_for_unpublished_course(self):
        """Unpublished courses are skipped."""
        unpublished = Course.objects.create(
            instructor=self.instructor,
            title="Draft Course",
            is_published=False,
        )

        from apps.analytics.tasks import refresh_analytics_cache
        refresh_analytics_cache()

        self.assertFalse(
            CourseAnalytics.objects.filter(course=unpublished).exists(),
            "Should not create analytics for unpublished course",
        )
