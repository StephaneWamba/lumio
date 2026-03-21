"""Certificates app views"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.utils import timezone
from django.shortcuts import get_object_or_404
import uuid
import structlog

from .models import CertificateTemplate, CertificateAward, EarnedCertificate
from .serializers import (
    CertificateTemplateSerializer,
    CertificateAwardSerializer,
    EarnedCertificateListSerializer,
    EarnedCertificateDetailSerializer,
)
from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from apps.users.permissions import IsInstructorOrReadOnly
from . import pdf_service, email_service

logger = structlog.get_logger()


class CertificateTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for certificate templates"""

    queryset = CertificateTemplate.objects.all()
    serializer_class = CertificateTemplateSerializer
    permission_classes = [IsAuthenticated, IsInstructorOrReadOnly]

    def get_queryset(self):
        """Filter templates by instructor ownership"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return CertificateTemplate.objects.all()
        if user.role == "instructor":
            return CertificateTemplate.objects.filter(course__instructor=user)
        # Students can see active templates for courses they're enrolled in
        return CertificateTemplate.objects.filter(
            is_active=True,
            course__enrollments__student=user,
        ).distinct()

    def perform_create(self, serializer):
        """Create certificate template for a course"""
        course = get_object_or_404(
            Course,
            id=self.request.data.get("course_id"),
        )
        # Verify instructor owns the course
        if self.request.user != course.instructor and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save()


class CertificateAwardViewSet(viewsets.ModelViewSet):
    """ViewSet for certificate award criteria"""

    queryset = CertificateAward.objects.all()
    serializer_class = CertificateAwardSerializer
    permission_classes = [IsAuthenticated, IsInstructorOrReadOnly]

    def get_queryset(self):
        """Filter awards by instructor ownership"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return CertificateAward.objects.all()
        if user.role == "instructor":
            return CertificateAward.objects.filter(course__instructor=user)
        return CertificateAward.objects.none()

    def perform_create(self, serializer):
        """Create award criteria for a course"""
        course = get_object_or_404(
            Course,
            id=self.request.data.get("course_id"),
        )
        # Verify instructor owns the course
        if self.request.user != course.instructor and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save()


class EarnedCertificateViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for earned certificates"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter earned certificates by user role"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return EarnedCertificate.objects.all()
        if user.role == "instructor":
            # Instructors see certificates for their courses
            return EarnedCertificate.objects.filter(enrollment__course__instructor=user)
        # Students see only their own certificates
        return EarnedCertificate.objects.filter(enrollment__student=user)

    def get_serializer_class(self):
        """Use detail serializer for retrieve"""
        if self.action == "retrieve":
            return EarnedCertificateDetailSerializer
        return EarnedCertificateListSerializer

    @action(detail=False, methods=["post"])
    def issue_for_enrollment(self, request):
        """Issue certificate for a specific enrollment"""
        enrollment_id = request.data.get("enrollment_id")
        if not enrollment_id:
            return Response(
                {"detail": "enrollment_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        enrollment = get_object_or_404(Enrollment, id=enrollment_id)

        # Verify instructor owns the course
        if request.user != enrollment.course.instructor and not request.user.is_staff:
            self.permission_denied(request)

        # Check if certificate already issued
        if hasattr(enrollment, "earned_certificate"):
            return Response(
                {"detail": "Certificate already issued for this enrollment"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Issue certificate
        template = get_object_or_404(
            CertificateTemplate,
            course=enrollment.course,
        )
        certificate = self._create_certificate(enrollment, template)

        serializer = EarnedCertificateDetailSerializer(certificate)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        """Revoke a certificate"""
        certificate = self.get_object()

        # Verify instructor owns the course
        if request.user != certificate.enrollment.course.instructor and not request.user.is_staff:
            self.permission_denied(request)

        if certificate.is_revoked:
            return Response(
                {"detail": "Certificate is already revoked"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        certificate.is_revoked = True
        certificate.revoked_at = timezone.now()
        certificate.revocation_reason = request.data.get(
            "reason",
            "Revoked by instructor",
        )
        certificate.save()

        serializer = EarnedCertificateDetailSerializer(certificate)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _create_certificate(self, enrollment, template):
        """Render PDF via WeasyPrint, upload to S3, email student, persist record."""
        certificate_number = (
            f"CERT-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        )
        completion_date = timezone.now().strftime("%B %d, %Y")

        rendered_content = template.content.format(
            student_name=enrollment.student.name,
            course_title=enrollment.course.title,
            completion_date=completion_date,
        )

        # Render PDF and upload to S3 (best-effort — don't block issuance if PDF fails)
        pdf_s3_key = None
        try:
            pdf_s3_key = pdf_service.render_and_upload(
                certificate_number=certificate_number,
                student_name=enrollment.student.name,
                course_title=enrollment.course.title,
                completion_date=completion_date,
                template=template,
            )
        except Exception:
            logger.warning(
                "certificate_pdf_failed",
                certificate_number=certificate_number,
            )

        certificate = EarnedCertificate.objects.create(
            enrollment=enrollment,
            template=template,
            certificate_number=certificate_number,
            rendered_content=rendered_content,
            pdf_s3_key=pdf_s3_key,
        )

        # Email student with PDF attached (best-effort — don't fail cert issuance if email fails)
        try:
            email_service.send_certificate_email(
                student_email=enrollment.student.email,
                student_name=enrollment.student.name,
                course_title=enrollment.course.title,
                certificate_number=certificate_number,
                pdf_s3_key=pdf_s3_key,
            )
        except Exception:
            logger.warning(
                "certificate_email_failed",
                certificate_number=certificate_number,
                student_email=enrollment.student.email,
            )

        return certificate


class CertificateVerifyView(APIView):
    """Public endpoint — no auth required — to verify a certificate by number."""

    permission_classes = [AllowAny]

    def get(self, request, certificate_number):
        cert = get_object_or_404(
            EarnedCertificate,
            certificate_number=certificate_number,
            is_revoked=False,
        )
        return Response({
            "certificate_number": cert.certificate_number,
            "student_name": cert.enrollment.student.name,
            "course_title": cert.enrollment.course.title,
            "issued_at": cert.created_at,
            "is_valid": True,
        })
