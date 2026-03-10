"""Tests for assessments and quizzes"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from decimal import Decimal

from apps.users.models import User
from apps.courses.models import Course, Section, Lesson
from apps.enrollments.models import Enrollment, LessonProgress
from .models import Quiz, Question, QuestionOption, QuizAttempt, AttemptAnswer


class QuizTests(TestCase):
    """Test quiz management"""

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
        self.quiz = Quiz.objects.create(
            lesson=self.lesson,
            title="Test Quiz",
            passing_score=70,
        )

    def test_quiz_list(self):
        """Test listing quizzes"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("quiz-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_quiz_detail(self):
        """Test quiz detail view"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("quiz-detail", args=[self.quiz.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "Test Quiz")


class QuizAttemptTests(TestCase):
    """Test quiz attempts and grading"""

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
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
        )
        self.lesson_progress = LessonProgress.objects.create(
            enrollment=self.enrollment,
            lesson=self.lesson,
        )
        self.quiz = Quiz.objects.create(
            lesson=self.lesson,
            title="Test Quiz",
            passing_score=70,
            allow_retake=True,
        )

        # Create questions
        self.mc_question = Question.objects.create(
            quiz=self.quiz,
            question_type=Question.QUESTION_TYPE_MULTIPLE_CHOICE,
            text="What is 2+2?",
            points=1,
            order=1,
        )
        QuestionOption.objects.create(
            question=self.mc_question,
            text="3",
            is_correct=False,
            order=1,
        )
        self.correct_option = QuestionOption.objects.create(
            question=self.mc_question,
            text="4",
            is_correct=True,
            order=2,
        )

    def test_start_attempt_requires_auth(self):
        """Test starting attempt requires authentication"""
        response = self.client.post(reverse("quiz-start-attempt", args=[self.quiz.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_start_attempt_not_enrolled(self):
        """Test starting attempt when not enrolled"""
        other_student = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.client.force_authenticate(user=other_student)
        response = self.client.post(reverse("quiz-start-attempt", args=[self.quiz.id]))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_start_attempt(self):
        """Test starting a quiz attempt"""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(reverse("quiz-start-attempt", args=[self.quiz.id]))
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "in_progress")
        self.assertEqual(response.data["attempt_number"], 1)

    def test_max_attempts_limit(self):
        """Test max attempts limit"""
        # Create a new lesson without a quiz for this test
        new_lesson = Lesson.objects.create(
            section=self.section,
            title="Lesson For Max Attempts",
            content="Content",
            order=99,
            is_published=True,
        )
        new_lesson_progress = LessonProgress.objects.create(
            enrollment=self.enrollment,
            lesson=new_lesson,
        )
        quiz = Quiz.objects.create(
            lesson=new_lesson,
            title="Limited Quiz",
            max_attempts=1,
            allow_retake=False,
        )
        # Create and submit first attempt
        attempt = QuizAttempt.objects.create(
            lesson_progress=new_lesson_progress,
            quiz=quiz,
            attempt_number=1,
            status=QuizAttempt.ATTEMPT_STATUS_GRADED,
            is_passed=True,
        )

        self.client.force_authenticate(user=self.student)
        response = self.client.post(reverse("quiz-start-attempt", args=[quiz.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_submit_quiz_multiple_choice(self):
        """Test submitting quiz with multiple choice answer"""
        # Start attempt
        self.client.force_authenticate(user=self.student)
        start_response = self.client.post(reverse("quiz-start-attempt", args=[self.quiz.id]))
        attempt_id = start_response.data["id"]

        # Submit with correct answer
        response = self.client.post(
            reverse("quiz-attempt-submit", args=[attempt_id]),
            {
                "answers": [
                    {
                        "question_id": self.mc_question.id,
                        "answer": self.correct_option.id,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "graded")
        self.assertTrue(response.data["is_passed"])
        self.assertEqual(response.data["percentage_score"], "100.00")

    def test_submit_quiz_incorrect_answer(self):
        """Test submitting quiz with incorrect answer"""
        self.client.force_authenticate(user=self.student)
        start_response = self.client.post(reverse("quiz-start-attempt", args=[self.quiz.id]))
        attempt_id = start_response.data["id"]

        # Get the incorrect option
        incorrect_option = self.mc_question.options.filter(is_correct=False).first()

        response = self.client.post(
            reverse("quiz-attempt-submit", args=[attempt_id]),
            {
                "answers": [
                    {
                        "question_id": self.mc_question.id,
                        "answer": incorrect_option.id,
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_passed"])
        self.assertEqual(response.data["percentage_score"], "0.00")

    def test_submit_quiz_updates_lesson_progress(self):
        """Test submitting quiz updates lesson progress"""
        self.client.force_authenticate(user=self.student)
        start_response = self.client.post(reverse("quiz-start-attempt", args=[self.quiz.id]))
        attempt_id = start_response.data["id"]

        self.client.post(
            reverse("quiz-attempt-submit", args=[attempt_id]),
            {
                "answers": [
                    {
                        "question_id": self.mc_question.id,
                        "answer": self.correct_option.id,
                    }
                ]
            },
            format="json",
        )

        self.lesson_progress.refresh_from_db()
        self.assertTrue(self.lesson_progress.quiz_passed)
        self.assertEqual(self.lesson_progress.highest_quiz_score, Decimal("100.00"))
        self.assertEqual(self.lesson_progress.quiz_attempts, 1)

    def test_quiz_attempt_not_submitted_twice(self):
        """Test cannot submit same attempt twice"""
        self.client.force_authenticate(user=self.student)
        start_response = self.client.post(reverse("quiz-start-attempt", args=[self.quiz.id]))
        attempt_id = start_response.data["id"]

        # Submit first time
        self.client.post(
            reverse("quiz-attempt-submit", args=[attempt_id]),
            {
                "answers": [
                    {
                        "question_id": self.mc_question.id,
                        "answer": self.correct_option.id,
                    }
                ]
            },
            format="json",
        )

        # Try to submit again
        response = self.client.post(
            reverse("quiz-attempt-submit", args=[attempt_id]),
            {
                "answers": [
                    {
                        "question_id": self.mc_question.id,
                        "answer": self.correct_option.id,
                    }
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
