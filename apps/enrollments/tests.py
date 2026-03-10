"""Tests for enrollments and progress tracking"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from decimal import Decimal

from apps.users.models import User
from apps.courses.models import Course, Section, Lesson
from .models import Enrollment, ProgressEvent, LessonProgress


class EnrollmentTests(TestCase):
    """Test enrollment management"""

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
        self.section = Section.objects.create(
            course=self.course,
            title="Test Section",
            order=1,
            is_published=True,
        )
        self.lesson1 = Lesson.objects.create(
            section=self.section,
            title="Lesson 1",
            content="Test content",
            order=1,
            is_published=True,
        )
        self.lesson2 = Lesson.objects.create(
            section=self.section,
            title="Lesson 2",
            content="Test content",
            order=2,
            is_published=True,
        )

    def test_enroll_requires_auth(self):
        """Test enrollment requires authentication"""
        response = self.client.post(
            reverse("enrollment-enroll"),
            {"course_id": self.course.id},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_enroll_in_course(self):
        """Test student can enroll in a course"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(
            reverse("enrollment-enroll"),
            {"course_id": self.course.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["student"]["id"], self.student1.id)
        self.assertEqual(response.data["course"]["id"], self.course.id)
        self.assertEqual(response.data["progress_percentage"], "0.00")

    def test_cannot_enroll_twice(self):
        """Test student cannot enroll in same course twice"""
        Enrollment.objects.create(student=self.student1, course=self.course)
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(
            reverse("enrollment-enroll"),
            {"course_id": self.course.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_enroll_nonexistent_course(self):
        """Test enrollment with non-existent course fails"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(
            reverse("enrollment-enroll"),
            {"course_id": 99999},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_own_enrollments(self):
        """Test student can see their enrollments"""
        enrollment = Enrollment.objects.create(student=self.student1, course=self.course)
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(reverse("enrollment-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], enrollment.id)


class LessonProgressTests(TestCase):
    """Test lesson progress tracking"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.student = User.objects.create_user(
            email="student@example.com",
            name="Test Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
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
        self.lesson1 = Lesson.objects.create(
            section=self.section,
            title="Lesson 1",
            content="Content 1",
            order=1,
            is_published=True,
        )
        self.lesson2 = Lesson.objects.create(
            section=self.section,
            title="Lesson 2",
            content="Content 2",
            order=2,
            is_published=True,
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
        )

    def test_mark_lesson_viewed_requires_auth(self):
        """Test marking lesson as viewed requires authentication"""
        response = self.client.post(
            reverse("enrollment-mark-lesson-viewed", args=[self.enrollment.id]),
            {"lesson_id": self.lesson1.id},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mark_lesson_viewed_permission_denied(self):
        """Test marking lesson as viewed by non-student fails"""
        other_student = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.client.force_authenticate(user=other_student)
        response = self.client.post(
            reverse("enrollment-mark-lesson-viewed", args=[self.enrollment.id]),
            {"lesson_id": self.lesson1.id},
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_mark_lesson_viewed(self):
        """Test marking lesson as viewed"""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("enrollment-mark-lesson-viewed", args=[self.enrollment.id]),
            {"lesson_id": self.lesson1.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["viewed_at"])

        # Check event was created
        event = ProgressEvent.objects.get(
            student=self.student,
            event_type=ProgressEvent.EVENT_LESSON_VIEWED,
        )
        self.assertEqual(event.lesson_id, self.lesson1.id)

    def test_mark_lesson_completed(self):
        """Test marking lesson as completed"""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("enrollment-mark-lesson-completed", args=[self.enrollment.id]),
            {"lesson_id": self.lesson1.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["completed_at"])

        # Check event was created
        event = ProgressEvent.objects.get(
            student=self.student,
            event_type=ProgressEvent.EVENT_LESSON_COMPLETED,
        )
        self.assertEqual(event.lesson_id, self.lesson1.id)

        # Check progress percentage is updated
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.progress_percentage, Decimal("50.00"))

    def test_course_completion_on_all_lessons(self):
        """Test course marked completed when all lessons completed"""
        self.client.force_authenticate(user=self.student)

        # Mark both lessons as completed
        self.client.post(
            reverse("enrollment-mark-lesson-completed", args=[self.enrollment.id]),
            {"lesson_id": self.lesson1.id},
        )
        self.client.post(
            reverse("enrollment-mark-lesson-completed", args=[self.enrollment.id]),
            {"lesson_id": self.lesson2.id},
        )

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.progress_percentage, Decimal("100.00"))
        self.assertIsNotNone(self.enrollment.completed_at)

    def test_get_enrollment_progress(self):
        """Test getting enrollment progress"""
        LessonProgress.objects.create(
            enrollment=self.enrollment,
            lesson=self.lesson1,
            viewed_at=None,
            completed_at=None,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("enrollment-progress", args=[self.enrollment.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)


class ProgressEventTests(TestCase):
    """Test progress event audit trail"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.student = User.objects.create_user(
            email="student@example.com",
            name="Test Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
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
        )
        self.lesson = Lesson.objects.create(
            section=self.section,
            title="Test Lesson",
            content="Test content",
            order=1,
        )

    def test_progress_event_list_requires_auth(self):
        """Test progress events require authentication"""
        response = self.client.get(reverse("progress-event-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_sees_only_own_events(self):
        """Test student can only see their own progress events"""
        other_student = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        ProgressEvent.objects.create(
            student=self.student,
            course=self.course,
            lesson=self.lesson,
            event_type=ProgressEvent.EVENT_LESSON_VIEWED,
        )
        ProgressEvent.objects.create(
            student=other_student,
            course=self.course,
            lesson=self.lesson,
            event_type=ProgressEvent.EVENT_LESSON_VIEWED,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("progress-event-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["student"], self.student.id)

    def test_instructor_sees_enrollments_progress(self):
        """Test instructor can see progress of enrolled students"""
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
        )
        ProgressEvent.objects.create(
            student=self.student,
            course=self.course,
            lesson=self.lesson,
            event_type=ProgressEvent.EVENT_LESSON_VIEWED,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(f"{reverse('progress-event-list')}?student_id={self.student.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
