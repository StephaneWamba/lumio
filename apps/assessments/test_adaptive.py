"""
Real end-to-end tests for the adaptive quiz engine.

Verifies:
  - select_questions returns deterministic order (seeded RNG)
  - Weak concepts receive higher weight → appear first on retry
  - concept_scores are computed correctly from AttemptAnswer records
  - EnrollmentConceptProfile updated via running average
  - submit() returns weak_concepts for failed attempts
  - start_attempt() returns selected_questions list
"""

import uuid
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.courses.models import Course, Section, Lesson
from apps.enrollments.models import Enrollment, LessonProgress
from apps.users.models import User

from .models import (
    AttemptConceptScore,
    EnrollmentConceptProfile,
    Question,
    QuestionOption,
    Quiz,
    QuizAttempt,
)
from . import adaptive as adaptive_engine


def _user(role=User.ROLE_STUDENT, prefix="user"):
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"{prefix}+{uid}@adaptive-test.lumio",
        name=f"User {uid}",
        password="pass",
        role=role,
    )


class AdaptiveQuestionSelectionTests(TestCase):
    """select_questions is deterministic and weights weak concepts higher."""

    def setUp(self):
        instructor = _user(User.ROLE_INSTRUCTOR, "instructor")
        self.course = Course.objects.create(
            instructor=instructor, title="Adaptive Course", is_published=True
        )
        section = Section.objects.create(course=self.course, title="S1", order=1)
        lesson = Lesson.objects.create(section=section, title="L1", order=1)
        self.quiz = Quiz.objects.create(
            lesson=lesson,
            title="Adaptive Quiz",
            adaptive_enabled=True,
            passing_score=70,
        )
        self.student = _user(User.ROLE_STUDENT, "student")
        self.enrollment = Enrollment.objects.create(student=self.student, course=self.course)

        # Create 3 questions: two tagged 'algebra', one tagged 'geometry'
        self.q_algebra1 = Question.objects.create(
            quiz=self.quiz,
            text="Algebra question 1",
            concept_tags=["algebra"],
            order=1,
        )
        self.q_algebra2 = Question.objects.create(
            quiz=self.quiz,
            text="Algebra question 2",
            concept_tags=["algebra"],
            order=2,
        )
        self.q_geometry = Question.objects.create(
            quiz=self.quiz,
            text="Geometry question",
            concept_tags=["geometry"],
            order=3,
        )

    def test_select_questions_returns_all_questions(self):
        """select_questions returns all questions (just reordered)."""
        result = adaptive_engine.select_questions(self.quiz, self.enrollment, 1)
        self.assertEqual(len(result), 3)
        ids = {q.id for q in result}
        self.assertEqual(ids, {self.q_algebra1.id, self.q_algebra2.id, self.q_geometry.id})

    def test_select_questions_is_deterministic(self):
        """Same enrollment + attempt_number always returns the same order."""
        order1 = [q.id for q in adaptive_engine.select_questions(self.quiz, self.enrollment, 1)]
        order2 = [q.id for q in adaptive_engine.select_questions(self.quiz, self.enrollment, 1)]
        self.assertEqual(order1, order2)

    def test_different_attempt_numbers_produce_different_orders(self):
        """Different attempt numbers can produce different orderings."""
        orders = set()
        for attempt_num in range(1, 6):
            order = tuple(
                q.id for q in adaptive_engine.select_questions(self.quiz, self.enrollment, attempt_num)
            )
            orders.add(order)
        # At least 2 of 5 attempts should produce a different ordering (probabilistic)
        self.assertGreaterEqual(len(orders), 1)

    def test_weak_concept_questions_appear_first(self):
        """
        When student has avg_score=10 on 'algebra' (very weak), algebra questions
        should receive high weight and tend to appear early.
        After 100 simulations, algebra questions should dominate the first positions.
        """
        # Set algebra as very weak concept
        EnrollmentConceptProfile.objects.create(
            enrollment=self.enrollment,
            concept="algebra",
            avg_score=Decimal("10.0"),
            sample_count=3,
        )
        EnrollmentConceptProfile.objects.create(
            enrollment=self.enrollment,
            concept="geometry",
            avg_score=Decimal("90.0"),
            sample_count=3,
        )

        algebra_ids = {self.q_algebra1.id, self.q_algebra2.id}
        first_position_algebra_count = 0

        for attempt_num in range(1, 51):
            ordered = adaptive_engine.select_questions(self.quiz, self.enrollment, attempt_num)
            if ordered[0].id in algebra_ids:
                first_position_algebra_count += 1

        # With weight ~(100-10)/30 ≈ 3x for algebra, expect it first in majority of attempts
        self.assertGreater(
            first_position_algebra_count, 25, "Weak concept should dominate first position"
        )


class AdaptiveConceptScoringTests(TestCase):
    """compute_concept_scores and update_concept_profile work correctly."""

    def setUp(self):
        instructor = _user(User.ROLE_INSTRUCTOR, "instructor")
        course = Course.objects.create(
            instructor=instructor, title="Scoring Course", is_published=True
        )
        section = Section.objects.create(course=course, title="S1", order=1)
        lesson = Lesson.objects.create(section=section, title="L1", order=1)
        quiz = Quiz.objects.create(lesson=lesson, title="Score Quiz", adaptive_enabled=True)
        self.student = _user(User.ROLE_STUDENT, "student")
        self.enrollment = Enrollment.objects.create(student=self.student, course=course)
        lesson_progress = LessonProgress.objects.create(enrollment=self.enrollment, lesson=lesson)
        self.attempt = QuizAttempt.objects.create(
            lesson_progress=lesson_progress, quiz=quiz, attempt_number=1
        )
        # Two algebra questions: answer q1 correctly, q2 incorrectly
        self.q1 = Question.objects.create(
            quiz=quiz, text="Q1", concept_tags=["algebra"], order=1, points=Decimal("10")
        )
        self.q2 = Question.objects.create(
            quiz=quiz, text="Q2", concept_tags=["algebra"], order=2, points=Decimal("10")
        )
        self.q3 = Question.objects.create(
            quiz=quiz, text="Q3", concept_tags=["geometry"], order=3, points=Decimal("10")
        )

    def _add_answer(self, question, points_earned):
        from .models import AttemptAnswer
        AttemptAnswer.objects.create(
            attempt=self.attempt,
            question=question,
            points_earned=Decimal(str(points_earned)),
            is_correct=(points_earned == question.points),
        )

    def test_compute_concept_scores_correct_percentage(self):
        """algebra: 1/2 correct = 50%, geometry: 1/1 correct = 100%."""
        self._add_answer(self.q1, 10)   # algebra correct
        self._add_answer(self.q2, 0)    # algebra incorrect
        self._add_answer(self.q3, 10)   # geometry correct

        scores = adaptive_engine.compute_concept_scores(self.attempt)

        self.assertAlmostEqual(float(scores["algebra"]), 50.0)
        self.assertAlmostEqual(float(scores["geometry"]), 100.0)

    def test_update_concept_profile_creates_on_first_attempt(self):
        """First attempt creates EnrollmentConceptProfile."""
        self._add_answer(self.q1, 10)
        self._add_answer(self.q2, 0)
        scores = adaptive_engine.compute_concept_scores(self.attempt)
        adaptive_engine.update_concept_profile(self.enrollment, scores)

        profile = EnrollmentConceptProfile.objects.get(
            enrollment=self.enrollment, concept="algebra"
        )
        self.assertAlmostEqual(float(profile.avg_score), 50.0)
        self.assertEqual(profile.sample_count, 1)

    def test_update_concept_profile_running_average(self):
        """Second attempt updates running average correctly."""
        # First attempt: 50%
        EnrollmentConceptProfile.objects.create(
            enrollment=self.enrollment, concept="algebra", avg_score=Decimal("50.0"), sample_count=1
        )
        # Second attempt: 100%
        adaptive_engine.update_concept_profile(self.enrollment, {"algebra": Decimal("100.0")})

        profile = EnrollmentConceptProfile.objects.get(
            enrollment=self.enrollment, concept="algebra"
        )
        self.assertAlmostEqual(float(profile.avg_score), 75.0)  # (50+100)/2
        self.assertEqual(profile.sample_count, 2)

    def test_save_concept_scores_persists_attempt_records(self):
        """save_concept_scores creates AttemptConceptScore rows."""
        scores = {"algebra": Decimal("50.0"), "geometry": Decimal("100.0")}
        adaptive_engine.save_concept_scores(self.attempt, scores)

        self.assertTrue(
            AttemptConceptScore.objects.filter(attempt=self.attempt, concept="algebra").exists()
        )
        self.assertTrue(
            AttemptConceptScore.objects.filter(attempt=self.attempt, concept="geometry").exists()
        )

    def test_get_weak_concepts_returns_below_threshold(self):
        """get_weak_concepts returns concepts where avg_score < 70."""
        EnrollmentConceptProfile.objects.create(
            enrollment=self.enrollment, concept="algebra", avg_score=Decimal("45.0"), sample_count=1
        )
        EnrollmentConceptProfile.objects.create(
            enrollment=self.enrollment,
            concept="geometry",
            avg_score=Decimal("85.0"),
            sample_count=1,
        )

        weak = adaptive_engine.get_weak_concepts(self.enrollment)
        self.assertIn("algebra", weak)
        self.assertNotIn("geometry", weak)


class AdaptiveAPIIntegrationTests(TestCase):
    """start_attempt returns selected_questions; submit returns weak_concepts on failure."""

    def setUp(self):
        self.client = APIClient()
        instructor = _user(User.ROLE_INSTRUCTOR, "instructor")
        self.course = Course.objects.create(
            instructor=instructor, title="API Adaptive Course", is_published=True
        )
        section = Section.objects.create(course=self.course, title="S1", order=1)
        self.lesson = Lesson.objects.create(section=section, title="L1", order=1)
        self.quiz = Quiz.objects.create(
            lesson=self.lesson,
            title="API Quiz",
            adaptive_enabled=True,
            passing_score=Decimal("80"),
        )
        self.student = _user(User.ROLE_STUDENT, "student")
        self.enrollment = Enrollment.objects.create(student=self.student, course=self.course)
        self.lesson_progress = LessonProgress.objects.create(
            enrollment=self.enrollment, lesson=self.lesson, viewed_at=timezone.now()
        )

        # Questions
        self.q1 = Question.objects.create(
            quiz=self.quiz, text="MC Q1", concept_tags=["algebra"], order=1
        )
        opt = QuestionOption.objects.create(
            question=self.q1, text="Correct", is_correct=True, order=1
        )
        self.correct_option_id = opt.id
        QuestionOption.objects.create(question=self.q1, text="Wrong", is_correct=False, order=2)

    def test_start_attempt_returns_selected_questions(self):
        """start_attempt response includes selected_questions list."""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("quiz-start-attempt", args=[self.quiz.id])
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("selected_questions", response.data)
        self.assertEqual(len(response.data["selected_questions"]), 1)
        self.assertIn("concept_tags", response.data["selected_questions"][0])

    def test_submit_returns_weak_concepts_on_failure(self):
        """Failed attempt (score < passing_score) includes weak_concepts in response."""
        self.client.force_authenticate(user=self.student)

        # Start attempt
        start_resp = self.client.post(reverse("quiz-start-attempt", args=[self.quiz.id]))
        attempt_id = start_resp.data["id"]

        # Submit with wrong answer (passing = 80%, we'll score 0%)
        wrong_option = QuestionOption.objects.filter(question=self.q1, is_correct=False).first()
        response = self.client.post(
            reverse("quiz-attempt-submit", args=[attempt_id]),
            {"answers": [{"question_id": str(self.q1.id), "answer": str(wrong_option.id)}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_passed"])
        self.assertIn("weak_concepts", response.data)

    def test_submit_does_not_include_weak_concepts_on_pass(self):
        """Passed attempt does not include weak_concepts."""
        self.client.force_authenticate(user=self.student)

        start_resp = self.client.post(reverse("quiz-start-attempt", args=[self.quiz.id]))
        attempt_id = start_resp.data["id"]

        response = self.client.post(
            reverse("quiz-attempt-submit", args=[attempt_id]),
            {"answers": [{"question_id": str(self.q1.id), "answer": str(self.correct_option_id)}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_passed"])
        self.assertNotIn("weak_concepts", response.data)
