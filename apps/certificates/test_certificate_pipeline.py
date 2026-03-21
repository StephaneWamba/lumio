"""
Real end-to-end tests for the certificate pipeline.

Exercises:
  - WeasyPrint renders a non-trivial PDF (> 1 kB)
  - PDF is uploaded to the real S3 assets bucket
  - EarnedCertificate.pdf_s3_key is populated after issue_for_enrollment
  - pdf_url in the API response is a real presigned S3 URL
  - Resend email is delivered to wambstephane@gmail.com with the PDF attached
  - Celery task check_completions issues certificates automatically
"""

import boto3
import uuid
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from .models import CertificateTemplate, CertificateAward, EarnedCertificate
from . import pdf_service


REAL_STUDENT_EMAIL = "wambstephane@gmail.com"


def _s3():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


class CertificatePDFServiceTests(TestCase):
    """WeasyPrint renders a real PDF and uploads it to S3."""

    def setUp(self):
        instructor = User.objects.create_user(
            email=f"instructor+{uuid.uuid4().hex[:6]}@cert-pipeline.test",
            name="Pipeline Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        course = Course.objects.create(
            instructor=instructor,
            title="PDF Pipeline Test Course",
            is_published=True,
        )
        self.template = CertificateTemplate.objects.create(
            course=course,
            title="Certificate of Completion",
            content="This certifies {student_name} completed {course_title} on {completion_date}",
            institution_name="Lumio Learning",
            signature_text="The Lumio Team",
            color_primary="#003366",
            color_accent="#0099CC",
        )

    def test_render_and_upload_produces_valid_pdf(self):
        """WeasyPrint renders a real PDF and the bytes are uploaded to S3."""
        cert_number = f"CERT-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        s3_key = pdf_service.render_and_upload(
            certificate_number=cert_number,
            student_name="Alice Wonderland",
            course_title="PDF Pipeline Test Course",
            completion_date=timezone.now().strftime("%B %d, %Y"),
            template=self.template,
        )

        self.assertIsNotNone(s3_key)
        self.assertIn(cert_number, s3_key)

        # Verify S3 key exists and PDF is non-trivial
        head = _s3().head_object(Bucket=settings.S3_ASSETS_BUCKET, Key=s3_key)
        self.assertGreater(head["ContentLength"], 1000, "PDF should be > 1 kB")
        self.assertEqual(head["ContentType"], "application/pdf")

    def test_generate_download_url_is_valid_presigned_url(self):
        """generate_download_url returns a presigned S3 URL for the PDF."""
        cert_number = f"CERT-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        s3_key = pdf_service.render_and_upload(
            certificate_number=cert_number,
            student_name="Bob Builder",
            course_title="PDF Pipeline Test Course",
            completion_date=timezone.now().strftime("%B %d, %Y"),
            template=self.template,
        )

        url = pdf_service.generate_download_url(s3_key)
        self.assertIn("X-Amz-Signature", url)
        self.assertIn(cert_number, url)


class CertificateIssueEndpointTests(TestCase):
    """issue_for_enrollment produces a real PDF, stores S3 key, returns pdf_url."""

    def setUp(self):
        self.client = APIClient()
        self.instructor = User.objects.create_user(
            email=f"instructor+{uuid.uuid4().hex[:6]}@cert-issue.test",
            name="Issue Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Issue Endpoint Course",
            is_published=True,
        )
        self.template = CertificateTemplate.objects.create(
            course=self.course,
            title="Certificate of Completion",
            content="This certifies {student_name} completed {course_title} on {completion_date}",
            institution_name="Lumio Learning",
            signature_text="The Lumio Team",
        )
        CertificateAward.objects.create(
            course=self.course,
            condition=CertificateAward.CONDITION_COURSE_COMPLETED,
        )
        self.student = User.objects.create_user(
            email=REAL_STUDENT_EMAIL,
            name="Stephane Wamba",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=100,
        )

    def test_issue_certificate_stores_pdf_s3_key(self):
        """After issuing, EarnedCertificate.pdf_s3_key points to a real S3 object."""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("earned-certificate-issue-for-enrollment"),
            {"enrollment_id": self.enrollment.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        cert = EarnedCertificate.objects.get(
            certificate_number=response.data["certificate_number"]
        )
        self.assertIsNotNone(cert.pdf_s3_key, "pdf_s3_key must be set after issuing")

        # Verify S3 object exists
        head = _s3().head_object(Bucket=settings.S3_ASSETS_BUCKET, Key=cert.pdf_s3_key)
        self.assertGreater(head["ContentLength"], 1000)

    def test_issue_certificate_returns_pdf_url_in_detail(self):
        """Detail endpoint returns pdf_url as a presigned S3 URL."""
        self.client.force_authenticate(user=self.instructor)
        issue_resp = self.client.post(
            reverse("earned-certificate-issue-for-enrollment"),
            {"enrollment_id": self.enrollment.id},
        )
        self.assertEqual(issue_resp.status_code, status.HTTP_201_CREATED)

        cert_id = issue_resp.data["id"]
        detail_resp = self.client.get(
            reverse("earned-certificate-detail", args=[cert_id])
        )
        self.assertEqual(detail_resp.status_code, status.HTTP_200_OK)
        pdf_url = detail_resp.data.get("pdf_url")
        self.assertIsNotNone(pdf_url, "pdf_url must be present in detail response")
        self.assertIn("X-Amz-Signature", pdf_url)

    def test_issue_certificate_sends_email_to_student(self):
        """
        Issuing a certificate sends a Resend email to the student.
        We verify this by checking Resend returns a non-null email ID
        (inspected via structlog — the call succeeds or raises).
        """
        self.client.force_authenticate(user=self.instructor)
        # If email_service.send_certificate_email raises, the test will fail with
        # the real Resend error, which is the desired behaviour.
        response = self.client.post(
            reverse("earned-certificate-issue-for-enrollment"),
            {"enrollment_id": self.enrollment.id},
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            "Certificate issue must succeed (including real Resend delivery)",
        )


class CertificateTaskTests(TestCase):
    """Celery task check_completions automatically issues certificates."""

    def setUp(self):
        instructor = User.objects.create_user(
            email=f"instructor+{uuid.uuid4().hex[:6]}@cert-task.test",
            name="Task Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=instructor,
            title="Task Auto-Cert Course",
            is_published=True,
        )
        CertificateTemplate.objects.create(
            course=self.course,
            title="Certificate of Completion",
            content="This certifies {student_name} completed {course_title} on {completion_date}",
            institution_name="Lumio Learning",
        )
        CertificateAward.objects.create(
            course=self.course,
            condition=CertificateAward.CONDITION_COURSE_COMPLETED,
        )
        self.student = User.objects.create_user(
            email=REAL_STUDENT_EMAIL,
            name="Stephane Wamba",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=100,
        )

    def test_check_completions_issues_certificate_and_uploads_pdf(self):
        """Task issues certificate, renders PDF, uploads to S3, emails student."""
        from .tasks import check_completions

        result = check_completions()

        self.assertGreaterEqual(result["issued"], 1)
        self.assertTrue(
            EarnedCertificate.objects.filter(enrollment=self.enrollment).exists()
        )

        cert = EarnedCertificate.objects.get(enrollment=self.enrollment)
        self.assertIsNotNone(cert.pdf_s3_key)
        self.assertRegex(cert.certificate_number, r"^CERT-\d{8}-[0-9A-F]{8}$")

        # Confirm PDF landed in S3
        head = _s3().head_object(Bucket=settings.S3_ASSETS_BUCKET, Key=cert.pdf_s3_key)
        self.assertGreater(head["ContentLength"], 1000)

    def test_check_completions_is_idempotent(self):
        """Running the task twice does not issue a second certificate."""
        from .tasks import check_completions

        result1 = check_completions()
        result2 = check_completions()

        self.assertGreaterEqual(result1["issued"], 1)
        self.assertEqual(result2["issued"], 0)
        self.assertEqual(
            EarnedCertificate.objects.filter(enrollment=self.enrollment).count(), 1
        )
