"""
Real end-to-end tests for Phase 8 email drip pipeline.

Every test sends to wambstephane@gmail.com via the real Resend API.
No mocks. If Resend is down the tests fail visibly — that's correct behaviour.
"""

import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.models import User
from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from .models import Notification, NotificationLog

REAL_EMAIL = "wambstephane@gmail.com"


def _unique_email(prefix="user"):
    return f"{prefix}+{uuid.uuid4().hex[:8]}@drip-test.lumio"


class ReengagementTaskTests(TestCase):
    """scan_reengagement sends real Resend emails to inactive students."""

    def setUp(self):
        instructor = User.objects.create_user(
            email=_unique_email("instructor"),
            name="Drip Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=instructor,
            title="Re-engagement Test Course",
            is_published=True,
        )
        self.student = User.objects.create_user(
            email=REAL_EMAIL,
            name="Stephane Wamba",
            password="pass",
            role=User.ROLE_STUDENT,
        )

    def _enroll(self, last_accessed_days_ago, progress=50):
        return Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=progress,
            last_accessed_at=timezone.now() - timedelta(days=last_accessed_days_ago),
        )

    def test_inactive_student_receives_notification_and_email(self):
        """Student inactive > 7 days gets in-app notification + real Resend email."""
        from .tasks import scan_reengagement

        self._enroll(last_accessed_days_ago=10)
        result = scan_reengagement()

        self.assertGreaterEqual(result["notified"], 1)

        notif = Notification.objects.get(
            user=self.student, subject__startswith="Continue your learning"
        )
        self.assertIn("Re-engagement Test Course", notif.subject)
        self.assertTrue(notif.email_sent, "email_sent must be True after Resend call")
        self.assertIsNotNone(notif.email_sent_at)

        log = NotificationLog.objects.get(
            notification=notif,
            log_type=NotificationLog.LOG_TYPE_EMAIL_SENT,
        )
        self.assertIn("resend_id", log.details)

    def test_recently_active_student_not_notified(self):
        """Student active 3 days ago (within cutoff) is not notified."""
        from .tasks import scan_reengagement

        self._enroll(last_accessed_days_ago=3)
        result = scan_reengagement()

        self.assertEqual(result["notified"], 0)
        self.assertFalse(
            Notification.objects.filter(
                user=self.student, subject__startswith="Continue your learning"
            ).exists()
        )

    def test_completed_course_student_not_notified(self):
        """Student who completed the course (100%) is not re-engaged."""
        from .tasks import scan_reengagement

        self._enroll(last_accessed_days_ago=10, progress=100)
        result = scan_reengagement()

        self.assertEqual(result["notified"], 0)

    def test_never_accessed_student_not_notified(self):
        """Student with last_accessed_at=None (never started) is excluded."""
        from .tasks import scan_reengagement

        Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=0,
            last_accessed_at=None,
        )
        result = scan_reengagement()

        self.assertEqual(result["notified"], 0)


class EnrollmentWelcomeTaskTests(TestCase):
    """send_enrollment_welcome sends a real welcome email on enrollment."""

    def setUp(self):
        instructor = User.objects.create_user(
            email=_unique_email("instructor"),
            name="Welcome Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=instructor,
            title="Welcome Email Course",
            is_published=True,
        )
        self.student = User.objects.create_user(
            email=REAL_EMAIL,
            name="Stephane Wamba",
            password="pass",
            role=User.ROLE_STUDENT,
        )

    def test_welcome_email_sent_on_enrollment(self):
        """Calling the task directly sends a Resend email and creates a notification."""
        from .tasks import send_enrollment_welcome

        # Create enrollment without triggering signal (CELERY_TASK_ALWAYS_EAGER
        # handles the signal path — we test the task directly here)
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
        )

        result = send_enrollment_welcome(enrollment.id)

        self.assertTrue(result["sent"])
        self.assertIn("email_id", result)

        notif = Notification.objects.get(
            user=self.student,
            notification_type=Notification.NOTIFICATION_TYPE_SUCCESS,
        )
        self.assertIn("Welcome Email Course", notif.subject)
        self.assertTrue(notif.email_sent)

        log = NotificationLog.objects.get(
            notification=notif,
            log_type=NotificationLog.LOG_TYPE_EMAIL_SENT,
        )
        self.assertIn("resend_id", log.details)

    def test_welcome_email_is_idempotent(self):
        """Calling the task twice for the same enrollment sends email only once."""
        from .tasks import send_enrollment_welcome

        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
        )

        result1 = send_enrollment_welcome(enrollment.id)
        result2 = send_enrollment_welcome(enrollment.id)

        self.assertTrue(result1["sent"])
        self.assertFalse(result2["sent"])
        self.assertEqual(result2["reason"], "already_sent")

        self.assertEqual(
            Notification.objects.filter(user=self.student).count(), 1
        )

    def test_signal_fires_task_on_enrollment_creation(self):
        """Creating an enrollment via the ORM fires the welcome task (ALWAYS_EAGER)."""
        # With CELERY_TASK_ALWAYS_EAGER=True the signal -> .delay() runs synchronously
        Enrollment.objects.create(
            student=self.student,
            course=self.course,
        )

        # Welcome notification should have been created synchronously
        self.assertTrue(
            Notification.objects.filter(
                user=self.student,
                notification_type=Notification.NOTIFICATION_TYPE_SUCCESS,
            ).exists(),
            "Welcome notification must be created when enrollment is saved",
        )
