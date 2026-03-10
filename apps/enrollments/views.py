"""Enrollments views: enrollment management and progress tracking"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
import structlog

from apps.courses.models import Course, Lesson
from apps.users.models import User
from .models import Enrollment, ProgressEvent, LessonProgress
from .serializers import (
    EnrollmentSerializer,
    EnrollCourseSerializer,
    ProgressEventSerializer,
    LessonProgressSerializer,
)

logger = structlog.get_logger()


class EnrollmentViewSet(viewsets.ModelViewSet):
    """Student enrollment management"""

    serializer_class = EnrollmentSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        """Filter enrollments by user"""
        if self.request.user.role == User.ROLE_STUDENT:
            return Enrollment.objects.filter(student=self.request.user)
        # Instructors see all enrollments in their courses
        return Enrollment.objects.filter(course__instructor=self.request.user)

    def perform_create(self, serializer):
        """Create enrollment"""
        serializer.save(student=self.request.user)

    @action(detail=False, methods=["post"])
    def enroll(self, request):
        """Enroll in a course"""
        serializer = EnrollCourseSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        course_id = serializer.validated_data["course_id"]
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response(
                {"error": "Course not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if already enrolled
        if Enrollment.objects.filter(student=request.user, course=course).exists():
            return Response(
                {"error": "Already enrolled in this course"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create enrollment
        enrollment = Enrollment.objects.create(
            student=request.user,
            course=course,
        )

        logger.info(
            "student_enrolled",
            student_id=request.user.id,
            course_id=course.id,
        )

        return Response(
            EnrollmentSerializer(enrollment).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def progress(self, request, pk=None):
        """Get enrollment progress (lesson completion status)"""
        enrollment = self.get_object()

        # Check access
        if request.user != enrollment.student and request.user != enrollment.course.instructor:
            return Response(
                {"error": "Access denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        lesson_progress = LessonProgress.objects.filter(enrollment=enrollment)
        serializer = LessonProgressSerializer(lesson_progress, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def mark_lesson_viewed(self, request, pk=None):
        """Record lesson view event"""
        enrollment = self.get_object()

        if request.user != enrollment.student:
            return Response(
                {"error": "Access denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        lesson_id = request.data.get("lesson_id")
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Record progress event
        ProgressEvent.objects.create(
            student=request.user,
            course=enrollment.course,
            lesson=lesson,
            event_type=ProgressEvent.EVENT_LESSON_VIEWED,
        )

        # Update/create lesson progress
        lesson_progress, _ = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson,
        )
        if not lesson_progress.viewed_at:
            lesson_progress.viewed_at = timezone.now()
            lesson_progress.save()

        # Update enrollment last_accessed_at
        enrollment.last_accessed_at = timezone.now()
        enrollment.save()

        logger.info(
            "lesson_viewed",
            student_id=request.user.id,
            lesson_id=lesson.id,
        )

        return Response(
            LessonProgressSerializer(lesson_progress).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def mark_lesson_completed(self, request, pk=None):
        """Mark lesson as completed"""
        enrollment = self.get_object()

        if request.user != enrollment.student:
            return Response(
                {"error": "Access denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        lesson_id = request.data.get("lesson_id")
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Record progress event
        ProgressEvent.objects.create(
            student=request.user,
            course=enrollment.course,
            lesson=lesson,
            event_type=ProgressEvent.EVENT_LESSON_COMPLETED,
        )

        # Update lesson progress
        lesson_progress, _ = LessonProgress.objects.get_or_create(
            enrollment=enrollment,
            lesson=lesson,
        )
        lesson_progress.completed_at = timezone.now()
        lesson_progress.save()

        # Recalculate course progress percentage
        from django.db.models import Count

        total_lessons = Lesson.objects.filter(section__course=enrollment.course).count()
        completed_lessons = LessonProgress.objects.filter(
            enrollment=enrollment,
            completed_at__isnull=False,
        ).count()

        if total_lessons > 0:
            progress = (completed_lessons / total_lessons) * 100
            enrollment.progress_percentage = progress

            if progress == 100:
                enrollment.completed_at = timezone.now()

            enrollment.save()

        logger.info(
            "lesson_completed",
            student_id=request.user.id,
            lesson_id=lesson.id,
            course_progress=enrollment.progress_percentage,
        )

        return Response(
            LessonProgressSerializer(lesson_progress).data,
            status=status.HTTP_200_OK,
        )


class ProgressEventViewSet(viewsets.ReadOnlyModelViewSet):
    """View progress event history (audit trail)"""

    serializer_class = ProgressEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter progress events by user and course"""
        course_id = self.request.query_params.get("course_id")
        student_id = self.request.query_params.get("student_id")

        queryset = ProgressEvent.objects.all()

        # Students see only their own events
        if self.request.user.role == User.ROLE_STUDENT:
            queryset = queryset.filter(student=self.request.user)

        # Filter by course if specified
        if course_id:
            queryset = queryset.filter(course_id=course_id)

        # Filter by student if specified (instructors can view their students)
        if student_id:
            try:
                enrollment = Enrollment.objects.get(
                    student_id=student_id,
                    course__instructor=self.request.user,
                )
                queryset = queryset.filter(student_id=student_id)
            except Enrollment.DoesNotExist:
                return ProgressEvent.objects.none()

        return queryset.order_by("-timestamp")
