"""Tests for notifications Celery tasks — re-engagement scanner."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.models import User
from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from .models import Notification


class ScanReengagementTaskTests(TestCase):
    """scan_reengagement() queues notifications for inactive students."""

    def setUp(self):
        self.instructor = User.objects.create_user(
            email="instructor@notif-tasks.com",
            name="Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Reengagement Test Course",
            is_published=True,
        )

    def _make_student(self, email, last_accessed_days_ago, progress=50):
        student = User.objects.create_user(
            email=email,
            name="Student",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        enrollment = Enrollment.objects.create(
            student=student,
            course=self.course,
            progress_percentage=progress,
            last_accessed_at=timezone.now() - timedelta(days=last_accessed_days_ago),
        )
        return student, enrollment

    def test_creates_notification_for_inactive_student(self):
        """Student inactive for >7 days with incomplete course gets a notification."""
        student, _ = self._make_student(
            "inactive@notif-tasks.com",
            last_accessed_days_ago=8,
            progress=40,
        )

        from apps.notifications.tasks import scan_reengagement

        scan_reengagement()

        self.assertTrue(
            Notification.objects.filter(user=student).exists(),
            "Inactive student should receive a re-engagement notification",
        )

    def test_does_not_notify_recently_active_student(self):
        """Student active within 7 days is not sent a re-engagement notification."""
        student, _ = self._make_student(
            "active@notif-tasks.com",
            last_accessed_days_ago=3,
            progress=40,
        )

        from apps.notifications.tasks import scan_reengagement

        scan_reengagement()

        self.assertFalse(
            Notification.objects.filter(user=student).exists(),
            "Recently active student should NOT receive re-engagement notification",
        )

    def test_does_not_notify_completed_course(self):
        """Student who completed the course is not sent a re-engagement notification."""
        student, _ = self._make_student(
            "completed@notif-tasks.com",
            last_accessed_days_ago=10,
            progress=100,
        )

        from apps.notifications.tasks import scan_reengagement

        scan_reengagement()

        self.assertFalse(
            Notification.objects.filter(user=student).exists(),
            "Completed enrollment should NOT trigger re-engagement",
        )

    def test_does_not_notify_student_with_no_access_date(self):
        """Enrollment with null last_accessed_at is skipped (no activity recorded)."""
        student = User.objects.create_user(
            email="noaccess@notif-tasks.com",
            name="No Access Student",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        Enrollment.objects.create(
            student=student,
            course=self.course,
            progress_percentage=0,
            last_accessed_at=None,
        )

        from apps.notifications.tasks import scan_reengagement

        scan_reengagement()

        self.assertFalse(
            Notification.objects.filter(user=student).exists(),
            "Student with no access date should not be targeted",
        )

    def test_returns_count_of_notified_students(self):
        """Task returns dict with count of students notified."""
        self._make_student("inactive1@notif-tasks.com", 8, 30)
        self._make_student("inactive2@notif-tasks.com", 15, 60)

        from apps.notifications.tasks import scan_reengagement

        result = scan_reengagement()

        self.assertIsInstance(result, dict)
        self.assertGreaterEqual(result["notified"], 2)
