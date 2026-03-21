"""Analytics app views"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.core.cache import cache
from django.db.models import Avg
from django.utils import timezone
from datetime import timedelta

ANALYTICS_CACHE_TTL = 3600  # 1 hour

from .models import (
    CourseAnalytics,
    LessonAnalytics,
    QuizAnalytics,
    StudentProgressSnapshot,
    EngagementMetric,
)
from .serializers import (
    CourseAnalyticsSerializer,
    LessonAnalyticsSerializer,
    QuizAnalyticsSerializer,
    StudentProgressSnapshotSerializer,
    EngagementMetricSerializer,
)
from apps.courses.models import Course
from apps.enrollments.models import Enrollment, LessonProgress


class CourseAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for course analytics"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter analytics by user role"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return CourseAnalytics.objects.all().select_related("course")
        if user.role == "instructor":
            return CourseAnalytics.objects.filter(course__instructor=user).select_related("course")
        return CourseAnalytics.objects.none()

    serializer_class = CourseAnalyticsSerializer

    def retrieve(self, request, *args, **kwargs):
        """Return cached analytics for a course (1h TTL)."""
        cache_key = f"analytics:course:{kwargs.get('pk')}"
        data = cache.get(cache_key)
        if data is None:
            response = super().retrieve(request, *args, **kwargs)
            cache.set(cache_key, response.data, ANALYTICS_CACHE_TTL)
            return response
        return Response(data)

    @action(detail=True, methods=["post"])
    def recalculate(self, request, pk=None):
        """Recalculate analytics for a course and invalidate cache."""
        analytics = self.get_object()

        if request.user != analytics.course.instructor and not request.user.is_staff:
            self.permission_denied(request)

        # Recalculate all metrics
        course = analytics.course
        enrollments = Enrollment.objects.filter(course=course)

        analytics.total_enrollments = enrollments.count()
        analytics.active_students = enrollments.filter(progress_percentage__gt=0).count()
        analytics.completed_students = enrollments.filter(progress_percentage=100).count()

        analytics.average_progress = (
            enrollments.aggregate(Avg("progress_percentage"))["progress_percentage__avg"] or 0
        )

        quiz_avg = LessonProgress.objects.filter(
            enrollment__course=course,
            highest_quiz_score__isnull=False,
        ).aggregate(Avg("highest_quiz_score"))["highest_quiz_score__avg"]

        if quiz_avg:
            analytics.average_quiz_score = quiz_avg

        analytics.save()

        # Invalidate cache so next retrieve reflects fresh data
        cache.delete(f"analytics:course:{analytics.pk}")

        serializer = CourseAnalyticsSerializer(analytics)
        return Response(serializer.data)


class LessonAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for lesson analytics"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter analytics by user role"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return LessonAnalytics.objects.all()
        if user.role == "instructor":
            return LessonAnalytics.objects.filter(lesson__section__course__instructor=user)
        return LessonAnalytics.objects.none()

    serializer_class = LessonAnalyticsSerializer


class QuizAnalyticsViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for quiz analytics"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter analytics by user role"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return QuizAnalytics.objects.all()
        if user.role == "instructor":
            return QuizAnalytics.objects.filter(quiz__lesson__section__course__instructor=user)
        return QuizAnalytics.objects.none()

    serializer_class = QuizAnalyticsSerializer


class StudentProgressSnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for student progress snapshots"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter snapshots by user role"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return StudentProgressSnapshot.objects.all()
        if user.role == "instructor":
            return StudentProgressSnapshot.objects.filter(enrollment__course__instructor=user)
        # Students see only their own snapshots
        return StudentProgressSnapshot.objects.filter(enrollment__student=user)

    serializer_class = StudentProgressSnapshotSerializer
    filterset_fields = ["enrollment", "snapshot_date"]
    ordering = ["-snapshot_date"]

    @action(detail=False, methods=["get"])
    def student_snapshots(self, request):
        """Get all snapshots for a specific student"""
        enrollment_id = request.query_params.get("enrollment_id")
        if not enrollment_id:
            return Response(
                {"detail": "enrollment_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        snapshots = StudentProgressSnapshot.objects.filter(enrollment__id=enrollment_id).order_by(
            "-snapshot_date"
        )

        serializer = StudentProgressSnapshotSerializer(snapshots, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def course_progress_trend(self, request):
        """Get progress trend for a course"""
        course_id = request.query_params.get("course_id")
        if not course_id:
            return Response(
                {"detail": "course_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify instructor access
        course = Course.objects.get(id=course_id)
        if request.user != course.instructor and not request.user.is_staff:
            self.permission_denied(request)

        # Get daily snapshots for past 30 days
        from django.db.models import Count

        thirty_days_ago = timezone.now().date() - timedelta(days=30)
        snapshots = (
            StudentProgressSnapshot.objects.filter(
                enrollment__course=course,
                snapshot_date__gte=thirty_days_ago,
            )
            .values("snapshot_date")
            .annotate(
                avg_progress=Avg("progress_percentage"),
                count=Count("id"),
            )
            .order_by("snapshot_date")
        )

        # Format response
        trend_data = [
            {
                "date": str(item["snapshot_date"]),
                "avg_progress": float(item["avg_progress"]),
                "count": item["count"],
            }
            for item in snapshots
        ]

        return Response(trend_data)


class EngagementMetricViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for engagement metrics"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter metrics by user role"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return EngagementMetric.objects.all()
        if user.role == "instructor":
            return EngagementMetric.objects.filter(course__instructor=user)
        return EngagementMetric.objects.none()

    serializer_class = EngagementMetricSerializer
    filterset_fields = ["course", "student", "metric_type"]

    @action(detail=False, methods=["get"])
    def top_engaged_students(self, request):
        """Get top engaged students for a course"""
        course_id = request.query_params.get("course_id")
        limit = int(request.query_params.get("limit", 10))

        if not course_id:
            return Response(
                {"detail": "course_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify instructor access
        course = Course.objects.get(id=course_id)
        if request.user != course.instructor and not request.user.is_staff:
            self.permission_denied(request)

        # Get top engaged students
        from django.db.models import Sum

        metrics = (
            EngagementMetric.objects.filter(course=course)
            .values("student__id", "student__name", "student__email")
            .annotate(total_engagement=Sum("count"))
            .order_by("-total_engagement")[:limit]
        )

        return Response(list(metrics))

    @action(detail=False, methods=["get"])
    def engagement_by_type(self, request):
        """Get engagement breakdown by metric type"""
        course_id = request.query_params.get("course_id")

        if not course_id:
            return Response(
                {"detail": "course_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify instructor access
        course = Course.objects.get(id=course_id)
        if request.user != course.instructor and not request.user.is_staff:
            self.permission_denied(request)

        # Aggregate by metric type
        from django.db.models import Sum, Count

        metrics = (
            EngagementMetric.objects.filter(course=course)
            .values("metric_type")
            .annotate(
                total_count=Sum("count"),
                unique_students=Count("student", distinct=True),
            )
            .order_by("-total_count")
        )

        return Response(list(metrics))
