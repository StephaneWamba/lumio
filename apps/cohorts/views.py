"""Cohorts views: cohort management and drip publishing"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
import structlog

from apps.courses.models import Course
from apps.users.models import User
from apps.enrollments.models import Enrollment
from .models import Cohort, CohortMember, DripSchedule
from .unlock import create_lesson_unlocks_for_schedule
from .serializers import (
    CohortListSerializer,
    CohortDetailSerializer,
    CohortMemberSerializer,
    DripScheduleSerializer,
)

logger = structlog.get_logger()


class CohortViewSet(viewsets.ModelViewSet):
    """Cohort management (instructors create, students join)"""

    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        """Filter cohorts by user role"""
        if self.request.user.role == User.ROLE_STUDENT:
            # Students see cohorts they're in or can join (distinct prevents duplicates)
            return (
                Cohort.objects.filter(course__is_published=True)
                | Cohort.objects.filter(members__student=self.request.user)
            ).distinct()
        # Instructors see cohorts for their courses
        return Cohort.objects.filter(course__instructor=self.request.user)

    def get_serializer_class(self):
        """Use detailed serializer for retrieve"""
        if self.action == "retrieve":
            return CohortDetailSerializer
        return CohortListSerializer

    def perform_create(self, serializer):
        """Create cohort (instructor only)"""
        course_id = self.request.data.get("course")
        try:
            course = Course.objects.get(id=course_id, instructor=self.request.user)
        except Course.DoesNotExist:
            raise PermissionError("Not authorized to create cohorts for this course")
        serializer.save(course=course)

    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        """Join a cohort as a student"""
        cohort = self.get_object()

        # Check if cohort is open
        if not cohort.is_open:
            return Response(
                {"error": "Cohort is not accepting new members"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Lock the cohort row to prevent concurrent over-enrollment
            cohort = Cohort.objects.select_for_update().get(pk=cohort.pk)

            # Check max students
            if cohort.max_students and cohort.member_count >= cohort.max_students:
                return Response(
                    {"error": "Cohort is full"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check already enrolled
            if CohortMember.objects.filter(cohort=cohort, student=request.user).exists():
                return Response(
                    {"error": "Already a member of this cohort"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create enrollment for the course first
            enrollment, _ = Enrollment.objects.get_or_create(
                student=request.user,
                course=cohort.course,
            )

            # Create cohort membership
            member = CohortMember.objects.create(
                cohort=cohort,
                student=request.user,
                enrollment=enrollment,
            )

        logger.info(
            "student_joined_cohort",
            student_id=request.user.id,
            cohort_id=cohort.id,
        )

        return Response(
            CohortMemberSerializer(member).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        """List cohort members"""
        cohort = self.get_object()
        members = cohort.members.filter(is_active=True)
        serializer = CohortMemberSerializer(members, many=True)
        return Response(serializer.data)


class DripScheduleViewSet(viewsets.ModelViewSet):
    """Drip schedule management and release"""

    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        """Filter drip schedules by user role"""
        if self.request.user.role == User.ROLE_STUDENT:
            # Students see schedules for cohorts they're in
            return DripSchedule.objects.filter(
                cohort__members__student=self.request.user,
                is_released=True,
            )
        # Instructors see schedules for their cohorts
        return DripSchedule.objects.filter(cohort__course__instructor=self.request.user)

    def get_serializer_class(self):
        return DripScheduleSerializer

    def perform_create(self, serializer):
        """Create drip schedule (instructor only)"""
        cohort_id = self.request.data.get("cohort")
        try:
            cohort = Cohort.objects.get(
                id=cohort_id,
                course__instructor=self.request.user,
            )
        except Cohort.DoesNotExist:
            raise PermissionError("Not authorized to create schedules for this cohort")
        serializer.save(cohort=cohort)

    @action(detail=False, methods=["post"])
    def release_pending(self, request):
        """Release all pending drip content (scheduled for now)"""
        if request.user.role != User.ROLE_INSTRUCTOR:
            return Response(
                {"error": "Only instructors can release content"},
                status=status.HTTP_403_FORBIDDEN,
            )

        now = timezone.now()
        pending = DripSchedule.objects.filter(
            cohort__course__instructor=request.user,
            is_active=True,
            is_released=False,
            release_at__lte=now,
        ) | DripSchedule.objects.filter(
            cohort__course__instructor=request.user,
            is_active=True,
            is_released=False,
            release_at__isnull=True,
        ).filter(
            cohort__start_date__lte=now - timedelta(days=1),
        )

        released_count = 0
        unlocks_created = 0
        for schedule in pending:
            if schedule.is_ready_to_release:
                with transaction.atomic():
                    schedule = DripSchedule.objects.select_for_update().get(pk=schedule.pk)
                    if schedule.is_released:
                        continue
                    schedule.is_released = True
                    schedule.released_at = now
                    schedule.save()
                    unlocks_created += create_lesson_unlocks_for_schedule(schedule)
                released_count += 1

                logger.info(
                    "drip_content_released",
                    cohort_id=schedule.cohort.id,
                    drip_type=schedule.drip_type,
                    unlocks_created=unlocks_created,
                )

        return Response(
            {
                "message": f"Released {released_count} pending drip schedules",
                "released_count": released_count,
                "unlocks_created": unlocks_created,
            }
        )

    @action(detail=True, methods=["post"])
    def manually_release(self, request, pk=None):
        """Manually release a drip schedule"""
        schedule = self.get_object()

        # Check instructor permission
        if request.user != schedule.cohort.course.instructor:
            return Response(
                {"error": "Only course instructor can release content"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if schedule.is_released:
            return Response(
                {"error": "Content already released"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            schedule = DripSchedule.objects.select_for_update().get(pk=schedule.pk)
            if schedule.is_released:
                return Response(
                    {"error": "Content already released"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            schedule.is_released = True
            schedule.released_at = timezone.now()
            schedule.save()
            unlocks_created = create_lesson_unlocks_for_schedule(schedule)

        logger.info(
            "drip_content_manually_released",
            cohort_id=schedule.cohort.id,
            schedule_id=schedule.id,
            unlocks_created=unlocks_created,
        )

        return Response(
            DripScheduleSerializer(schedule).data,
            status=status.HTTP_200_OK,
        )
