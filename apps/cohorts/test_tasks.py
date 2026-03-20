"""Tests for cohorts Celery tasks — drip unlock scanner."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.models import User
from apps.courses.models import Course, Section, Lesson
from apps.enrollments.models import Enrollment
from .models import Cohort, CohortMember, DripSchedule


class ScanAndReleaseDripTaskTests(TestCase):
    """scan_and_release_drip() releases all due DripSchedules."""

    def setUp(self):
        self.instructor = User.objects.create_user(
            email="instructor@cohort-tasks.com",
            name="Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            email="student@cohort-tasks.com",
            name="Student",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Task Test Course",
            is_published=True,
        )
        self.section = Section.objects.create(
            course=self.course,
            title="Section 1",
            order=1,
        )
        self.lesson = Lesson.objects.create(
            section=self.section,
            title="Lesson 1",
            order=1,
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
        )
        # Cohort that started 2 days ago
        self.cohort = Cohort.objects.create(
            course=self.course,
            name="March Cohort",
            start_date=timezone.now() - timedelta(days=2),
        )
        CohortMember.objects.create(
            cohort=self.cohort,
            student=self.student,
            enrollment=self.enrollment,
        )

    def test_task_releases_due_drip_schedule(self):
        """Task marks DripSchedule is_released=True when scheduled time has passed."""
        schedule = DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type=DripSchedule.DRIP_TYPE_LESSON,
            lesson=self.lesson,
            days_after_start=1,  # 1 day after start — already past
            is_released=False,
        )

        from apps.cohorts.tasks import scan_and_release_drip

        scan_and_release_drip()

        schedule.refresh_from_db()
        self.assertTrue(schedule.is_released, "DripSchedule should be marked released")
        self.assertIsNotNone(schedule.released_at, "released_at should be set")

    def test_task_does_not_release_future_schedule(self):
        """Task does not release DripSchedules scheduled for the future."""
        schedule = DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type=DripSchedule.DRIP_TYPE_LESSON,
            lesson=self.lesson,
            days_after_start=10,  # 10 days — not yet due
            is_released=False,
        )

        from apps.cohorts.tasks import scan_and_release_drip

        scan_and_release_drip()

        schedule.refresh_from_db()
        self.assertFalse(schedule.is_released, "Future schedule should NOT be released")

    def test_task_does_not_re_release_already_released(self):
        """Task is idempotent — already released schedules stay unchanged."""
        released_at = timezone.now() - timedelta(hours=1)
        schedule = DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type=DripSchedule.DRIP_TYPE_LESSON,
            lesson=self.lesson,
            days_after_start=1,
            is_released=True,
            released_at=released_at,
        )

        from apps.cohorts.tasks import scan_and_release_drip

        scan_and_release_drip()

        schedule.refresh_from_db()
        # released_at should not have been updated
        self.assertEqual(
            schedule.released_at.replace(microsecond=0),
            released_at.replace(microsecond=0),
            "Idempotent: already released schedule should not be touched",
        )

    def test_task_returns_released_count(self):
        """Task returns count of newly released schedules."""
        DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type=DripSchedule.DRIP_TYPE_LESSON,
            lesson=self.lesson,
            days_after_start=1,
            is_released=False,
        )

        from apps.cohorts.tasks import scan_and_release_drip

        result = scan_and_release_drip()

        self.assertIsInstance(result, dict)
        self.assertGreaterEqual(result["released"], 1)
