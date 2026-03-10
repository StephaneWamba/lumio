"""Certificates app URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CertificateTemplateViewSet,
    CertificateAwardViewSet,
    EarnedCertificateViewSet,
)

router = DefaultRouter()
router.register(r"templates", CertificateTemplateViewSet, basename="certificate-template")
router.register(r"awards", CertificateAwardViewSet, basename="certificate-award")
router.register(r"earned", EarnedCertificateViewSet, basename="earned-certificate")

urlpatterns = [
    path("", include(router.urls)),
]
