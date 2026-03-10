"""Cohorts app URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CohortViewSet, DripScheduleViewSet

router = DefaultRouter()
router.register(r"cohorts", CohortViewSet, basename="cohort")
router.register(r"drip-schedules", DripScheduleViewSet, basename="drip-schedule")

urlpatterns = [
    path("", include(router.urls)),
]
