"""Analytics app URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CourseAnalyticsViewSet,
    LessonAnalyticsViewSet,
    QuizAnalyticsViewSet,
    StudentProgressSnapshotViewSet,
    EngagementMetricViewSet,
)

router = DefaultRouter()
router.register(r"courses", CourseAnalyticsViewSet, basename="course-analytics")
router.register(r"lessons", LessonAnalyticsViewSet, basename="lesson-analytics")
router.register(r"quizzes", QuizAnalyticsViewSet, basename="quiz-analytics")
router.register(r"progress-snapshots", StudentProgressSnapshotViewSet, basename="progress-snapshot")
router.register(r"engagement", EngagementMetricViewSet, basename="engagement-metric")

urlpatterns = [
    path("", include(router.urls)),
]
