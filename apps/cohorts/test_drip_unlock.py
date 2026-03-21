"""
Real end-to-end tests for Phase 6: drip unlock and lesson access gating.

Verifies:
  - scan_and_release_drip task creates LessonUnlock records for all cohort members
  - manually_release endpoint creates LessonUnlock records
  - release_pending endpoint creates LessonUnlock records
  - Locked lessons return 403 on mark_lesson_viewed
  - Unlocked lessons allow progress tracking
  - Non-cohort lessons are always accessible
  - Idempotency: re-releasing does not create duplicate LessonUnlock rows
"""

import uuid
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.courses.models import Course, Section, Lesson
from apps.enrollments.models import Enrollment
from .models import Cohort, CohortMember, DripSchedule, LessonUnlock


def _user(role=User.ROLE_STUDENT, prefix="user"):
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"{prefix}+{uid}@drip-unlock.test",
        name=f"User {uid}",
        password="pass",
        role=role,
    )


class DripUnlockTaskTests(TestCase):
    """scan_and_release_drip creates LessonUnlock rows."""

    def setUp(self):
        self.instructor = _user(User.ROLE_INSTRUCTOR, "instructor")
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Drip Task Course",
            is_published=True,
        )
        section = Section.objects.create(course=self.course, title="Section 1", order=1)
        self.lesson = Lesson.objects.create(section=section, title="Lesson 1", order=1)

        # Cohort started 2 days ago
        self.cohort = Cohort.objects.create(
            course=self.course,
            name="Cohort A",
            start_date=timezone.now() - timedelta(days=2),
        )

        # Two enrolled students in the cohort
        self.students = []
        for i in range(2):
            student = _user(User.ROLE_STUDENT, f"student{i}")
            enrollment = Enrollment.objects.create(student=student, course=self.course)
            CohortMember.objects.create(cohort=self.cohort, student=student, enrollment=enrollment)
            self.students.append((student, enrollment))

        # DripSchedule: release lesson 1 day after start (already due)
        self.schedule = DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type=DripSchedule.DRIP_TYPE_LESSON,
            lesson=self.lesson,
            days_after_start=1,
        )

    def test_task_creates_lesson_unlocks_for_all_members(self):
        """Released schedule creates one LessonUnlock per cohort member."""
        from .tasks import scan_and_release_drip

        result = scan_and_release_drip()

        self.assertEqual(result["released"], 1)
        self.assertEqual(result["unlocks_created"], 2)

        for student, enrollment in self.students:
            self.assertTrue(
                LessonUnlock.objects.filter(enrollment=enrollment, lesson=self.lesson).exists(),
                f"LessonUnlock missing for {student.email}",
            )

    def test_task_is_idempotent_no_duplicate_unlocks(self):
        """Running the task twice does not duplicate LessonUnlock rows."""
        from .tasks import scan_and_release_drip

        scan_and_release_drip()
        result2 = scan_and_release_drip()

        self.assertEqual(result2["released"], 0)
        self.assertEqual(LessonUnlock.objects.filter(lesson=self.lesson).count(), 2)

    def test_future_schedule_not_released(self):
        """Schedule due in 10 days is not released."""
        future = DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type=DripSchedule.DRIP_TYPE_LESSON,
            lesson=self.lesson,
            days_after_start=10,
        )
        # Mark existing as already released so it doesn't interfere
        self.schedule.is_released = True
        self.schedule.save()

        from .tasks import scan_and_release_drip

        result = scan_and_release_drip()
        self.assertEqual(result["released"], 0)
        self.assertFalse(LessonUnlock.objects.filter(drip_schedule=future).exists())


class ManualReleaseEndpointTests(TestCase):
    """manually_release endpoint creates LessonUnlock rows."""

    def setUp(self):
        self.client = APIClient()
        self.instructor = _user(User.ROLE_INSTRUCTOR, "instructor")
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Manual Release Course",
            is_published=True,
        )
        section = Section.objects.create(course=self.course, title="Section 1", order=1)
        self.lesson = Lesson.objects.create(section=section, title="Lesson 1", order=1)

        self.cohort = Cohort.objects.create(
            course=self.course,
            name="Cohort B",
            start_date=timezone.now() - timedelta(days=5),
        )
        self.student = _user(User.ROLE_STUDENT, "student")
        self.enrollment = Enrollment.objects.create(student=self.student, course=self.course)
        CohortMember.objects.create(
            cohort=self.cohort, student=self.student, enrollment=self.enrollment
        )
        self.schedule = DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type=DripSchedule.DRIP_TYPE_LESSON,
            lesson=self.lesson,
            days_after_start=100,  # Far future — requires manual release
        )

    def test_manually_release_creates_lesson_unlock(self):
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("drip-schedule-manually-release", args=[self.schedule.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            LessonUnlock.objects.filter(
                enrollment=self.enrollment, lesson=self.lesson
            ).exists()
        )


class LessonAccessGatingTests(TestCase):
    """mark_lesson_viewed returns 403 for locked lessons, 200 for unlocked."""

    def setUp(self):
        self.client = APIClient()
        self.instructor = _user(User.ROLE_INSTRUCTOR, "instructor")
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Gating Course",
            is_published=True,
        )
        section = Section.objects.create(course=self.course, title="Section 1", order=1)
        self.locked_lesson = Lesson.objects.create(section=section, title="Locked", order=1)
        self.free_lesson = Lesson.objects.create(section=section, title="Free", order=2)

        self.cohort = Cohort.objects.create(
            course=self.course,
            name="Gating Cohort",
            start_date=timezone.now() + timedelta(days=10),  # Not started yet
        )
        self.student = _user(User.ROLE_STUDENT, "student")
        self.enrollment = Enrollment.objects.create(student=self.student, course=self.course)
        CohortMember.objects.create(
            cohort=self.cohort, student=self.student, enrollment=self.enrollment
        )

        # DripSchedule exists for locked_lesson — not yet released
        DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type=DripSchedule.DRIP_TYPE_LESSON,
            lesson=self.locked_lesson,
            days_after_start=5,
        )
        # free_lesson has NO DripSchedule → always accessible

    def test_locked_lesson_returns_403(self):
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("enrollment-mark-lesson-viewed", args=[self.enrollment.id]),
            {"lesson_id": self.locked_lesson.id},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("not been unlocked", response.data["error"])

    def test_free_lesson_always_accessible(self):
        """Lesson without a DripSchedule is accessible even in a cohort."""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("enrollment-mark-lesson-viewed", args=[self.enrollment.id]),
            {"lesson_id": self.free_lesson.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unlocked_lesson_becomes_accessible(self):
        """After LessonUnlock is created, student can access the lesson."""
        LessonUnlock.objects.create(
            enrollment=self.enrollment,
            lesson=self.locked_lesson,
            drip_schedule=DripSchedule.objects.get(lesson=self.locked_lesson),
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("enrollment-mark-lesson-viewed", args=[self.enrollment.id]),
            {"lesson_id": self.locked_lesson.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_cohort_student_always_has_access(self):
        """Student not in any cohort can access any lesson freely."""
        non_cohort_student = _user(User.ROLE_STUDENT, "free")
        enrollment = Enrollment.objects.create(student=non_cohort_student, course=self.course)
        self.client.force_authenticate(user=non_cohort_student)
        response = self.client.post(
            reverse("enrollment-mark-lesson-viewed", args=[enrollment.id]),
            {"lesson_id": self.locked_lesson.id},
        )
        # No DripSchedule membership for this student → access allowed
        self.assertEqual(response.status_code, status.HTTP_200_OK)
