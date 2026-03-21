"""Tests for analytics"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from decimal import Decimal

from apps.users.models import User
from apps.courses.models import Course, Section, Lesson
from apps.enrollments.models import Enrollment
from apps.assessments.models import Quiz
from .models import (
    CourseAnalytics,
    LessonAnalytics,
    QuizAnalytics,
    StudentProgressSnapshot,
    EngagementMetric,
)


class CourseAnalyticsTests(TestCase):
    """Test course analytics"""

    def setUp(self):
        """Set up test data"""
        self.client: APIClient = APIClient()
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
            is_published=True,
        )
        self.analytics = CourseAnalytics.objects.create(
            course=self.course,
            total_enrollments=1,
            average_progress=Decimal("50.00"),
        )

    def test_list_analytics_requires_auth(self):
        """Test listing analytics requires auth"""
        response = self.client.get(reverse("course-analytics-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_instructor_sees_their_analytics(self):
        """Test instructor sees their course analytics"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("course-analytics-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_student_cannot_see_analytics(self):
        """Test student cannot see analytics"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("course-analytics-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_retrieve_analytics(self):
        """Test retrieving analytics detail"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("course-analytics-detail", args=[self.analytics.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_enrollments"], 1)

    def test_recalculate_analytics(self):
        """Test recalculating course analytics"""
        Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=Decimal("75.00"),
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("course-analytics-recalculate", args=[self.analytics.id])
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_enrollments"], 1)


class LessonAnalyticsTests(TestCase):
    """Test lesson analytics"""

    def setUp(self):
        """Set up test data"""
        self.client: APIClient = APIClient()
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
            title="Section 1",
            order=1,
        )
        self.lesson = Lesson.objects.create(
            section=self.section,
            title="Lesson 1",
            content="Content",
            order=1,
        )
        self.analytics = LessonAnalytics.objects.create(
            lesson=self.lesson,
            total_views=10,
            unique_viewers=8,
        )

    def test_list_lesson_analytics(self):
        """Test listing lesson analytics"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("lesson-analytics-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_retrieve_lesson_analytics(self):
        """Test retrieving lesson analytics detail"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("lesson-analytics-detail", args=[self.analytics.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_views"], 10)


class QuizAnalyticsTests(TestCase):
    """Test quiz analytics"""

    def setUp(self):
        """Set up test data"""
        self.client: APIClient = APIClient()
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
            title="Section 1",
            order=1,
        )
        self.lesson = Lesson.objects.create(
            section=self.section,
            title="Lesson 1",
            content="Content",
            order=1,
        )
        self.quiz = Quiz.objects.create(
            lesson=self.lesson,
            title="Quiz 1",
        )
        self.analytics = QuizAnalytics.objects.create(
            quiz=self.quiz,
            total_attempts=10,
            unique_test_takers=5,
            pass_rate=Decimal("80.00"),
        )

    def test_list_quiz_analytics(self):
        """Test listing quiz analytics"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("quiz-analytics-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_retrieve_quiz_analytics(self):
        """Test retrieving quiz analytics detail"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("quiz-analytics-detail", args=[self.analytics.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pass_rate"], "80.00")


class StudentProgressSnapshotTests(TestCase):
    """Test student progress snapshots"""

    def setUp(self):
        """Set up test data"""
        self.client: APIClient = APIClient()
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
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=Decimal("50.00"),
        )

    def test_create_snapshot(self):
        """Test creating progress snapshot"""
        snapshot = StudentProgressSnapshot.objects.create(
            enrollment=self.enrollment,
            progress_percentage=Decimal("50.00"),
            lessons_completed=2,
            quizzes_passed=1,
            total_time_spent_minutes=120,
        )
        self.assertEqual(snapshot.progress_percentage, Decimal("50.00"))

    def test_list_student_snapshots(self):
        """Test listing student's own snapshots"""
        StudentProgressSnapshot.objects.create(
            enrollment=self.enrollment,
            progress_percentage=Decimal("50.00"),
            lessons_completed=2,
            quizzes_passed=1,
            total_time_spent_minutes=120,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("progress-snapshot-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_student_cannot_see_others_snapshots(self):
        """Test student cannot see other student's snapshots"""
        other_student = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        StudentProgressSnapshot.objects.create(
            enrollment=self.enrollment,
            progress_percentage=Decimal("50.00"),
            lessons_completed=2,
            quizzes_passed=1,
            total_time_spent_minutes=120,
        )
        self.client.force_authenticate(user=other_student)
        response = self.client.get(reverse("progress-snapshot-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_instructor_sees_student_snapshots(self):
        """Test instructor sees their students' snapshots"""
        StudentProgressSnapshot.objects.create(
            enrollment=self.enrollment,
            progress_percentage=Decimal("50.00"),
            lessons_completed=2,
            quizzes_passed=1,
            total_time_spent_minutes=120,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("progress-snapshot-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_unique_snapshot_per_day(self):
        """Test only one snapshot per student per day"""
        with self.assertRaises(Exception):
            StudentProgressSnapshot.objects.create(
                enrollment=self.enrollment,
                progress_percentage=Decimal("50.00"),
                lessons_completed=2,
                quizzes_passed=1,
                total_time_spent_minutes=120,
            )
            # Try to create another on the same day
            StudentProgressSnapshot.objects.create(
                enrollment=self.enrollment,
                progress_percentage=Decimal("60.00"),
                lessons_completed=3,
                quizzes_passed=1,
                total_time_spent_minutes=130,
            )


class EngagementMetricTests(TestCase):
    """Test engagement metrics"""

    def setUp(self):
        """Set up test data"""
        self.client: APIClient = APIClient()
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
        )

    def test_create_engagement_metric(self):
        """Test creating engagement metric"""
        metric = EngagementMetric.objects.create(
            course=self.course,
            student=self.student,
            metric_type=EngagementMetric.METRIC_TYPE_LESSON_VIEW,
            count=5,
        )
        self.assertEqual(metric.count, 5)

    def test_list_engagement_metrics(self):
        """Test listing engagement metrics"""
        EngagementMetric.objects.create(
            course=self.course,
            student=self.student,
            metric_type=EngagementMetric.METRIC_TYPE_LESSON_VIEW,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("engagement-metric-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_top_engaged_students(self):
        """Test getting top engaged students"""
        EngagementMetric.objects.create(
            course=self.course,
            student=self.student,
            metric_type=EngagementMetric.METRIC_TYPE_LESSON_VIEW,
            count=10,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(
            reverse("engagement-metric-top-engaged-students"),
            {"course_id": self.course.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        top = response.data[0]
        self.assertEqual(top["student__email"], self.student.email)
        self.assertEqual(top["total_engagement"], 10)

    def test_engagement_by_type(self):
        """Test getting engagement breakdown by type"""
        EngagementMetric.objects.create(
            course=self.course,
            student=self.student,
            metric_type=EngagementMetric.METRIC_TYPE_LESSON_VIEW,
            count=5,
        )
        EngagementMetric.objects.create(
            course=self.course,
            student=self.student,
            metric_type=EngagementMetric.METRIC_TYPE_QUIZ_ATTEMPT,
            count=3,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(
            reverse("engagement-metric-engagement-by-type"),
            {"course_id": self.course.id},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        # Results are ordered by -total_count, so lesson_view (5) comes first
        by_type = {row["metric_type"]: row for row in response.data}
        self.assertIn(EngagementMetric.METRIC_TYPE_LESSON_VIEW, by_type)
        self.assertIn(EngagementMetric.METRIC_TYPE_QUIZ_ATTEMPT, by_type)
        self.assertEqual(by_type[EngagementMetric.METRIC_TYPE_LESSON_VIEW]["total_count"], 5)
        self.assertEqual(by_type[EngagementMetric.METRIC_TYPE_QUIZ_ATTEMPT]["total_count"], 3)
        self.assertEqual(by_type[EngagementMetric.METRIC_TYPE_LESSON_VIEW]["unique_students"], 1)
