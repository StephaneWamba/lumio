"""Assessments views: quiz management and grading"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.shortcuts import get_object_or_404
from decimal import Decimal
import structlog

from apps.enrollments.models import Enrollment, LessonProgress
from apps.courses.models import Lesson
from apps.users.models import User
from .models import Quiz, Question, QuestionOption, QuizAttempt, AttemptAnswer
from .serializers import (
    QuizListSerializer,
    QuizDetailSerializer,
    QuizAttemptListSerializer,
    QuizAttemptDetailSerializer,
    StartQuizAttemptSerializer,
    SubmitQuizAttemptSerializer,
    AttemptAnswerSerializer,
)

logger = structlog.get_logger()


class QuizViewSet(viewsets.ReadOnlyModelViewSet):
    """Quiz management (read-only for students)"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter quizzes by course enrollment"""
        lesson_id = self.kwargs.get("lesson_id")
        if lesson_id:
            return Quiz.objects.filter(lesson_id=lesson_id)
        return Quiz.objects.all()

    def get_serializer_class(self):
        """Use detailed serializer for retrieve"""
        if self.action == "retrieve":
            return QuizDetailSerializer
        return QuizListSerializer

    @action(detail=True, methods=["post"])
    def start_attempt(self, request, pk=None):
        """Start a new quiz attempt"""
        quiz = self.get_object()
        lesson = quiz.lesson

        # Get enrollment
        try:
            enrollment = Enrollment.objects.get(
                student=request.user,
                course=lesson.section.course,
            )
        except Enrollment.DoesNotExist:
            return Response(
                {"error": "Not enrolled in this course"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get lesson progress
        lesson_progress = get_object_or_404(
            LessonProgress,
            enrollment=enrollment,
            lesson=lesson,
        )

        # Check max attempts
        if quiz.max_attempts:
            attempt_count = QuizAttempt.objects.filter(
                lesson_progress=lesson_progress,
                quiz=quiz,
            ).count()
            if attempt_count >= quiz.max_attempts:
                return Response(
                    {"error": f"Maximum {quiz.max_attempts} attempts reached"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # Check if previous attempt passed (no retake)
        last_attempt = (
            QuizAttempt.objects.filter(
                lesson_progress=lesson_progress,
                quiz=quiz,
            )
            .order_by("-attempt_number")
            .first()
        )

        if last_attempt and last_attempt.is_passed and not quiz.allow_retake:
            return Response(
                {"error": "Already passed this quiz"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create new attempt
        attempt_number = (last_attempt.attempt_number + 1) if last_attempt else 1
        attempt = QuizAttempt.objects.create(
            lesson_progress=lesson_progress,
            quiz=quiz,
            attempt_number=attempt_number,
        )

        # Update lesson progress attempt counter
        lesson_progress.quiz_attempts += 1
        lesson_progress.save()

        logger.info(
            "quiz_attempt_started",
            student_id=request.user.id,
            quiz_id=quiz.id,
            attempt_number=attempt_number,
        )

        return Response(
            QuizAttemptDetailSerializer(attempt).data,
            status=status.HTTP_201_CREATED,
        )


class QuizAttemptViewSet(viewsets.ModelViewSet):
    """Quiz attempt management and grading"""

    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        """Filter attempts by user"""
        if self.request.user.role == User.ROLE_STUDENT:
            # Students see only their attempts
            return QuizAttempt.objects.filter(
                lesson_progress__enrollment__student=self.request.user
            )
        # Instructors see attempts in their courses
        return QuizAttempt.objects.filter(
            quiz__lesson__section__course__instructor=self.request.user
        )

    def get_serializer_class(self):
        """Use detailed serializer for retrieve"""
        if self.action == "retrieve":
            return QuizAttemptDetailSerializer
        return QuizAttemptListSerializer

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        """Submit quiz attempt with answers"""
        attempt = self.get_object()

        # Check permission
        if (
            request.user != attempt.lesson_progress.enrollment.student
            and request.user != attempt.quiz.lesson.section.course.instructor
        ):
            return Response(
                {"error": "Access denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check if already submitted
        if attempt.status != QuizAttempt.ATTEMPT_STATUS_IN_PROGRESS:
            return Response(
                {"error": "Attempt already submitted"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = SubmitQuizAttemptSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Process answers and grade automatically for objective questions
        answers_data = serializer.validated_data["answers"]
        total_points = Decimal("0")
        earned_points = Decimal("0")

        for answer_data in answers_data:
            question_id = answer_data.get("question_id")
            answer_value = answer_data.get("answer")

            try:
                question = Question.objects.get(id=question_id, quiz=attempt.quiz)
            except Question.DoesNotExist:
                continue

            total_points += question.points

            # Process answer based on question type
            if question.question_type == Question.QUESTION_TYPE_MULTIPLE_CHOICE:
                try:
                    option = QuestionOption.objects.get(id=answer_value)
                    is_correct = option.is_correct
                    points = question.points if is_correct else Decimal("0")
                except QuestionOption.DoesNotExist:
                    is_correct = False
                    points = Decimal("0")

                AttemptAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    selected_option_id=answer_value,
                    is_correct=is_correct,
                    points_earned=points,
                )

                if is_correct:
                    earned_points += points

            elif question.question_type == Question.QUESTION_TYPE_TRUE_FALSE:
                is_correct = (
                    answer_value.lower() == "true"
                    and question.options.filter(text="True", is_correct=True).exists()
                ) or (
                    answer_value.lower() == "false"
                    and question.options.filter(text="False", is_correct=True).exists()
                )
                points = question.points if is_correct else Decimal("0")

                AttemptAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    text_answer=answer_value,
                    is_correct=is_correct,
                    points_earned=points,
                )

                if is_correct:
                    earned_points += points

            else:
                # Short answer / essay - pending manual grading
                AttemptAnswer.objects.create(
                    attempt=attempt,
                    question=question,
                    text_answer=answer_value,
                    is_correct=None,
                    points_earned=None,
                )

        # Mark attempt as submitted
        attempt.status = QuizAttempt.ATTEMPT_STATUS_SUBMITTED
        attempt.submitted_at = timezone.now()
        attempt.score = earned_points
        attempt.percentage_score = (
            (earned_points / total_points * 100) if total_points > 0 else Decimal("0")
        )
        attempt.is_passed = attempt.percentage_score >= attempt.quiz.passing_score
        attempt.status = QuizAttempt.ATTEMPT_STATUS_GRADED
        attempt.save()

        # Update lesson progress
        lesson_progress = attempt.lesson_progress
        if attempt.is_passed:
            lesson_progress.quiz_passed = True
            lesson_progress.quiz_passed_at = timezone.now()
            lesson_progress.highest_quiz_score = max(
                lesson_progress.highest_quiz_score or Decimal("0"),
                attempt.percentage_score,
            )
        lesson_progress.save()

        logger.info(
            "quiz_attempt_submitted",
            student_id=request.user.id,
            quiz_id=attempt.quiz.id,
            score=attempt.percentage_score,
            passed=attempt.is_passed,
        )

        return Response(
            QuizAttemptDetailSerializer(attempt).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def grade_answer(self, request, pk=None):
        """Manually grade an essay/short answer (instructor only)"""
        attempt = self.get_object()

        # Check instructor permission
        if request.user != attempt.quiz.lesson.section.course.instructor:
            return Response(
                {"error": "Only instructors can grade"},
                status=status.HTTP_403_FORBIDDEN,
            )

        answer_id = request.data.get("answer_id")
        points = request.data.get("points")
        notes = request.data.get("notes", "")

        try:
            answer = AttemptAnswer.objects.get(id=answer_id, attempt=attempt)
        except AttemptAnswer.DoesNotExist:
            return Response(
                {"error": "Answer not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Update answer with grade
        answer.points_earned = Decimal(str(points))
        answer.is_correct = points >= answer.question.points / 2
        answer.grading_notes = notes
        answer.graded_by = f"{request.user.name}"
        answer.graded_at = timezone.now()
        answer.save()

        logger.info(
            "answer_graded",
            instructor_id=request.user.id,
            answer_id=answer_id,
            points=points,
        )

        return Response(
            AttemptAnswerSerializer(answer).data,
            status=status.HTTP_200_OK,
        )
