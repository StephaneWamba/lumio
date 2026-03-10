"""Notifications app URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    NotificationTemplateViewSet,
    NotificationPreferenceViewSet,
    NotificationViewSet,
    NotificationLogViewSet,
)

router = DefaultRouter()
router.register(r"templates", NotificationTemplateViewSet, basename="notification-template")
router.register(r"preferences", NotificationPreferenceViewSet, basename="notification-preference")
router.register(r"", NotificationViewSet, basename="notification")
router.register(r"logs", NotificationLogViewSet, basename="notification-log")

urlpatterns = [
    path("", include(router.urls)),
]
