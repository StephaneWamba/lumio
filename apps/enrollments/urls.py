"""Enrollments app URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EnrollmentViewSet, ProgressEventViewSet

router = DefaultRouter()
router.register(r"enrollments", EnrollmentViewSet, basename="enrollment")
router.register(r"progress-events", ProgressEventViewSet, basename="progress-event")

urlpatterns = [
    path("", include(router.urls)),
]
