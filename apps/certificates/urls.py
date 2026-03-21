"""Certificates app URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CertificateTemplateViewSet,
    CertificateAwardViewSet,
    EarnedCertificateViewSet,
    CertificateVerifyView,
)

router = DefaultRouter()
router.register(r"templates", CertificateTemplateViewSet, basename="certificate-template")
router.register(r"awards", CertificateAwardViewSet, basename="certificate-award")
router.register(r"earned", EarnedCertificateViewSet, basename="earned-certificate")

urlpatterns = [
    path("", include(router.urls)),
    path("verify/<str:certificate_number>/", CertificateVerifyView.as_view(), name="certificate-verify"),
]
