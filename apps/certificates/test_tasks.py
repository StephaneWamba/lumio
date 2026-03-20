"""Tests for certificates Celery tasks — completion detection."""

from django.test import TestCase
from django.utils import timezone

from apps.users.models import User
from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from .models import CertificateTemplate, CertificateAward, EarnedCertificate


class CheckCompletionsTaskTests(TestCase):
    """check_completions() creates EarnedCertificate for 100% enrollments."""

    def setUp(self):
        self.instructor = User.objects.create_user(
            email="instructor@cert-tasks.com",
            name="Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            email="student@cert-tasks.com",
            name="Student",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Cert Test Course",
            is_published=True,
        )
        self.template = CertificateTemplate.objects.create(
            course=self.course,
            title="Certificate of Completion",
            content="Awarded to {student_name} for completing {course_title}.",
        )
        self.award = CertificateAward.objects.create(
            course=self.course,
            condition=CertificateAward.CONDITION_COURSE_COMPLETED,
        )

    def test_creates_certificate_for_completed_enrollment(self):
        """Enrollment at 100% with no cert — task creates EarnedCertificate."""
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=100,
            completed_at=timezone.now(),
        )

        from apps.certificates.tasks import check_completions

        check_completions()

        self.assertTrue(
            EarnedCertificate.objects.filter(enrollment=enrollment).exists(),
            "EarnedCertificate should be created for 100% enrollment",
        )

    def test_does_not_duplicate_existing_certificate(self):
        """Task is idempotent — does not create duplicate certificate."""
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=100,
            completed_at=timezone.now(),
        )
        EarnedCertificate.objects.create(
            enrollment=enrollment,
            template=self.template,
            certificate_number="EXISTING-001",
            rendered_content="Already rendered",
        )

        from apps.certificates.tasks import check_completions

        check_completions()

        count = EarnedCertificate.objects.filter(enrollment=enrollment).count()
        self.assertEqual(count, 1, "Should not create a duplicate certificate")

    def test_does_not_create_certificate_for_incomplete_enrollment(self):
        """Enrollment below 100% — no certificate created."""
        enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=80,
        )

        from apps.certificates.tasks import check_completions

        check_completions()

        self.assertFalse(
            EarnedCertificate.objects.filter(enrollment=enrollment).exists(),
            "No certificate for incomplete enrollment",
        )

    def test_certificate_number_is_unique(self):
        """Each generated certificate has a unique certificate_number."""
        student2 = User.objects.create_user(
            email="student2@cert-tasks.com",
            name="Student Two",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        e1 = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=100,
            completed_at=timezone.now(),
        )
        e2 = Enrollment.objects.create(
            student=student2,
            course=self.course,
            progress_percentage=100,
            completed_at=timezone.now(),
        )

        from apps.certificates.tasks import check_completions

        check_completions()

        cert1 = EarnedCertificate.objects.get(enrollment=e1)
        cert2 = EarnedCertificate.objects.get(enrollment=e2)
        self.assertNotEqual(
            cert1.certificate_number,
            cert2.certificate_number,
            "Certificate numbers must be unique",
        )
