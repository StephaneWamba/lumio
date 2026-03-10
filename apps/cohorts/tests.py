"""Tests for cohorts and drip publishing"""
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from datetime import timedelta

from apps.users.models import User
from apps.courses.models import Course, Section, Lesson
from .models import Cohort, CohortMember, DripSchedule


class CohortTests(TestCase):
    """Test cohort management"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@example.com",
            name="Test Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.student1 = User.objects.create_user(
            email="student1@example.com",
            name="Student One",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.student2 = User.objects.create_user(
            email="student2@example.com",
            name="Student Two",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Test Course",
            is_published=True,
        )
        self.start_date = timezone.now() + timedelta(days=1)
        self.cohort = Cohort.objects.create(
            course=self.course,
            name="Cohort 1",
            start_date=self.start_date,
            is_open=True,
        )

    def test_list_cohorts_requires_auth(self):
        """Test listing cohorts requires authentication"""
        response = self.client.get(reverse("cohort-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_instructor_sees_their_cohorts(self):
        """Test instructor can see their cohorts"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("cohort-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_student_sees_published_cohorts(self):
        """Test student can see published course cohorts"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(reverse("cohort-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_join_cohort(self):
        """Test student can join a cohort"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(
            reverse("cohort-join", args=[self.cohort.id])
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            CohortMember.objects.filter(
                cohort=self.cohort,
                student=self.student1,
            ).exists()
        )

    def test_cannot_join_twice(self):
        """Test student cannot join same cohort twice"""
        CohortMember.objects.create(
            cohort=self.cohort,
            student=self.student1,
            enrollment=self.course.enrollments.first() or
                       self.course.enrollments.create(student=self.student1),
        )
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(
            reverse("cohort-join", args=[self.cohort.id])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_join_closed_cohort(self):
        """Test student cannot join closed cohort"""
        closed_cohort = Cohort.objects.create(
            course=self.course,
            name="Closed Cohort",
            start_date=self.start_date,
            is_open=False,
        )
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(
            reverse("cohort-join", args=[closed_cohort.id])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cohort_max_students_limit(self):
        """Test cohort max students limit"""
        limited_cohort = Cohort.objects.create(
            course=self.course,
            name="Limited Cohort",
            start_date=self.start_date,
            max_students=1,
            is_open=True,
        )
        # First student joins
        enrollment1 = self.course.enrollments.create(student=self.student1)
        CohortMember.objects.create(
            cohort=limited_cohort,
            student=self.student1,
            enrollment=enrollment1,
        )

        # Second student tries to join
        self.client.force_authenticate(user=self.student2)
        response = self.client.post(
            reverse("cohort-join", args=[limited_cohort.id])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_list_cohort_members(self):
        """Test listing cohort members"""
        enrollment = self.course.enrollments.create(student=self.student1)
        CohortMember.objects.create(
            cohort=self.cohort,
            student=self.student1,
            enrollment=enrollment,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(
            reverse("cohort-members", args=[self.cohort.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class DripScheduleTests(TestCase):
    """Test drip publishing schedules"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@example.com",
            name="Test Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Test Course",
            is_published=True,
        )
        self.section = Section.objects.create(
            course=self.course,
            title="Test Section",
            order=1,
            is_published=True,
        )
        self.lesson = Lesson.objects.create(
            section=self.section,
            title="Test Lesson",
            content="Test content",
            order=1,
            is_published=True,
        )
        self.start_date = timezone.now() + timedelta(days=1)
        self.cohort = Cohort.objects.create(
            course=self.course,
            name="Test Cohort",
            start_date=self.start_date,
        )

    def test_create_drip_schedule(self):
        """Test creating drip schedule"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("dripschedule-list"),
            {
                "cohort": self.cohort.id,
                "drip_type": "lesson",
                "lesson": self.lesson.id,
                "days_after_start": 3,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["days_after_start"], 3)

    def test_drip_schedule_scheduled_release_time(self):
        """Test drip schedule calculates release time"""
        schedule = DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type="lesson",
            lesson=self.lesson,
            days_after_start=5,
        )
        expected = self.start_date + timedelta(days=5)
        self.assertEqual(schedule.scheduled_release_time, expected)

    def test_drip_schedule_absolute_release(self):
        """Test drip schedule with absolute release time"""
        release_time = timezone.now() + timedelta(days=2)
        schedule = DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type="lesson",
            lesson=self.lesson,
            release_at=release_time,
        )
        self.assertEqual(schedule.scheduled_release_time, release_time)

    def test_manually_release_drip(self):
        """Test manually releasing drip content"""
        schedule = DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type="lesson",
            lesson=self.lesson,
            days_after_start=10,
            is_released=False,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("dripschedule-manually-release", args=[schedule.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_released"])

    def test_cannot_release_already_released(self):
        """Test cannot release already released content"""
        schedule = DripSchedule.objects.create(
            cohort=self.cohort,
            drip_type="lesson",
            lesson=self.lesson,
            is_released=True,
            released_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("dripschedule-manually-release", args=[schedule.id])
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
