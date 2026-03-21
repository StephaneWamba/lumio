"""Tests for course content management"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from .models import Course, Section, Lesson


class CourseTests(TestCase):
    """Test course CRUD and permissions"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@example.com",
            name="Test Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            email="student@example.com",
            name="Test Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Test Course",
            description="Test Description",
            price=9.99,
            is_published=True,
        )

    def test_list_published_courses(self):
        """Test listing published courses"""
        response = self.client.get(reverse("course-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)

    def test_list_unpublished_courses_as_student(self):
        """Test student can't see unpublished courses"""
        Course.objects.create(
            instructor=self.instructor,
            title="Unpublished Course",
            is_published=False,
        )
        response = self.client.get(reverse("course-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should only see published course
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["id"], self.course.id)

    def test_list_all_courses_as_instructor(self):
        """Test instructor can see all their courses"""
        Course.objects.create(
            instructor=self.instructor,
            title="Unpublished Course",
            is_published=False,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("course-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see both published and unpublished
        self.assertEqual(len(response.data["results"]), 2)

    def test_create_course_as_instructor(self):
        """Test instructor can create courses"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("course-list"),
            {
                "title": "New Course",
                "description": "New Description",
                "price": 19.99,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "New Course")
        self.assertEqual(response.data["instructor"]["id"], self.instructor.id)

    def test_create_course_as_student_fails(self):
        """Test student cannot create courses"""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("course-list"),
            {
                "title": "New Course",
                "price": 19.99,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_own_course(self):
        """Test instructor can update their own course"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.patch(
            reverse("course-detail", args=[self.course.id]),
            {"title": "Updated Title"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.course.refresh_from_db()
        self.assertEqual(self.course.title, "Updated Title")

    def test_publish_course(self):
        """Test publishing a course"""
        unpublished = Course.objects.create(
            instructor=self.instructor,
            title="Unpublished",
            is_published=False,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("course-publish", args=[unpublished.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        unpublished.refresh_from_db()
        self.assertTrue(unpublished.is_published)


class SectionTests(TestCase):
    """Test section CRUD"""

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

    def test_list_sections(self):
        """Test listing sections returns correct section data"""
        response = self.client.get(reverse("course-sections", args=[self.course.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [s["title"] for s in response.data]
        self.assertIn(self.section.title, titles)

    def test_create_section(self):
        """Test creating a section"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("course-sections", args=[self.course.id]),
            {
                "title": "New Section",
                "order": 2,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "New Section")

    def test_create_section_wrong_instructor_fails(self):
        """Test non-instructor cannot create section"""
        other_instructor = User.objects.create_user(
            email="other@example.com",
            name="Other Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.client.force_authenticate(user=other_instructor)
        response = self.client.post(
            reverse("course-sections", args=[self.course.id]),
            {
                "title": "New Section",
                "order": 2,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class LessonTests(TestCase):
    """Test lesson CRUD"""

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

    def test_list_lessons(self):
        """Test listing lessons returns correct lesson data"""
        response = self.client.get(
            reverse("section-lessons", args=[self.course.id, self.section.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [l["title"] for l in response.data]
        self.assertIn(self.lesson.title, titles)

    def test_create_lesson(self):
        """Test creating a lesson"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("section-lessons", args=[self.course.id, self.section.id]),
            {
                "title": "New Lesson",
                "content": "New content",
                "order": 2,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "New Lesson")

    def test_lesson_prerequisite(self):
        """Test setting lesson prerequisites"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.patch(
            reverse("lesson-detail", args=[self.course.id, self.section.id, self.lesson.id]),
            {
                "prerequisite_lesson": self.lesson.id,
            },
        )
        # Can't have self as prerequisite in real scenario, but testing the field works
        self.assertEqual(response.status_code, status.HTTP_200_OK)
