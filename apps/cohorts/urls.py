"""Cohorts app URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CohortViewSet, DripScheduleViewSet, LessonUnlockViewSet

router = DefaultRouter()
router.register(r"cohorts", CohortViewSet, basename="cohort")
router.register(r"drip-schedules", DripScheduleViewSet, basename="drip-schedule")
router.register(r"lesson-unlocks", LessonUnlockViewSet, basename="lesson-unlock")

urlpatterns = [
    path("", include(router.urls)),
]
