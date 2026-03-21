"""Tests for certificates"""

import uuid
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User, InstructorProfile
from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from .models import CertificateTemplate, CertificateAward, EarnedCertificate


def _make_certificate_number():
    """Generate a certificate number matching the real system format."""
    return f"CERT-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"


def _render_content(template, enrollment):
    """Render certificate content the same way _create_certificate does."""
    return template.content.format(
        student_name=enrollment.student.name,
        course_title=enrollment.course.title,
        completion_date=timezone.now().strftime("%B %d, %Y"),
    )


class CertificateTemplateTests(TestCase):
    """Test certificate template management"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@example.com",
            name="Test Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Test Course",
            is_published=True,
        )

    def test_create_certificate_template(self):
        """Test creating certificate template"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("certificate-template-list"),
            {
                "course_id": self.course.id,
                "title": "Certificate of Completion",
                "content": "This certifies that {student_name} has completed {course_title}",
                "institution_name": "Test University",
                "signature_text": "John Doe, Dean",
                "color_primary": "#003366",
                "color_accent": "#0099CC",
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["title"], "Certificate of Completion")

    def test_template_list_requires_auth(self):
        """Test listing templates requires authentication"""
        response = self.client.get(reverse("certificate-template-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_instructor_sees_their_templates(self):
        """Test instructor sees their templates"""
        CertificateTemplate.objects.create(
            course=self.course,
            title="Test Template",
            content="Test content",
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("certificate-template-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_cannot_create_template_for_others_course(self):
        """Test instructor cannot create template for other's course"""
        other_instructor = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        other_course = Course.objects.create(
            instructor=other_instructor,
            title="Other Course",
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("certificate-template-list"),
            {
                "course_id": other_course.id,
                "title": "Template",
                "content": "Content",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CertificateAwardTests(TestCase):
    """Test certificate award criteria"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@example.com",
            name="Test Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        InstructorProfile.objects.create(user=self.instructor, is_approved=True)
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Test Course",
            is_published=True,
        )

    def test_create_award_criteria(self):
        """Test creating award criteria"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("certificate-award-list"),
            {
                "course_id": self.course.id,
                "condition": "course_completed",
                "minimum_score": 70,
                "is_active": True,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["condition"], "course_completed")

    def test_award_criteria_requires_instructor(self):
        """Test award criteria creation requires instructor"""
        student = User.objects.create_user(
            email="student@example.com",
            name="Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.client.force_authenticate(user=student)
        response = self.client.post(
            reverse("certificate-award-list"),
            {
                "course_id": self.course.id,
                "condition": "course_completed",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_check_eligibility_course_completed(self):
        """Test eligibility check for course completion"""
        award = CertificateAward.objects.create(
            course=self.course,
            condition=CertificateAward.CONDITION_COURSE_COMPLETED,
        )
        student = User.objects.create_user(
            email="student@example.com",
            name="Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        enrollment = Enrollment.objects.create(
            student=student,
            course=self.course,
            progress_percentage=100,
        )
        self.assertTrue(award.check_eligibility(enrollment))

    def test_check_eligibility_incomplete_course(self):
        """Test eligibility check fails for incomplete course"""
        award = CertificateAward.objects.create(
            course=self.course,
            condition=CertificateAward.CONDITION_COURSE_COMPLETED,
        )
        student = User.objects.create_user(
            email="student@example.com",
            name="Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        enrollment = Enrollment.objects.create(
            student=student,
            course=self.course,
            progress_percentage=50,
        )
        self.assertFalse(award.check_eligibility(enrollment))


class EarnedCertificateTests(TestCase):
    """Test earned certificates"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@example.com",
            name="Test Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            email="wambstephane@gmail.com",
            name="Test Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Test Course",
            is_published=True,
        )
        self.template = CertificateTemplate.objects.create(
            course=self.course,
            title="Certificate",
            content="This certifies {student_name} completed {course_title}",
            institution_name="Test Uni",
        )
        self.award = CertificateAward.objects.create(
            course=self.course,
            condition=CertificateAward.CONDITION_COURSE_COMPLETED,
        )
        self.enrollment = Enrollment.objects.create(
            student=self.student,
            course=self.course,
            progress_percentage=100,
        )

    def test_issue_certificate(self):
        """Test issuing a certificate"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("earned-certificate-issue-for-enrollment"),
            {"enrollment_id": self.enrollment.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data["certificate_number"])
        self.assertFalse(response.data["is_revoked"])

    def test_cannot_issue_twice(self):
        """Test cannot issue same certificate twice"""
        EarnedCertificate.objects.create(
            enrollment=self.enrollment,
            template=self.template,
            certificate_number=_make_certificate_number(),
            rendered_content=_render_content(self.template, self.enrollment),
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("earned-certificate-issue-for-enrollment"),
            {"enrollment_id": self.enrollment.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_issue_ineligible_student(self):
        """Test cannot issue certificate to ineligible student"""
        ineligible_student = User.objects.create_user(
            email="ineligible@example.com",
            name="Ineligible Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        incomplete_enrollment = Enrollment.objects.create(
            student=ineligible_student,
            course=self.course,
            progress_percentage=50,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("earned-certificate-issue-for-enrollment"),
            {"enrollment_id": incomplete_enrollment.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_sees_own_certificates(self):
        """Test student can see their own certificates"""
        cert_number = _make_certificate_number()
        EarnedCertificate.objects.create(
            enrollment=self.enrollment,
            template=self.template,
            certificate_number=cert_number,
            rendered_content=_render_content(self.template, self.enrollment),
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("earned-certificate-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["certificate_number"], cert_number)
        self.assertRegex(result["certificate_number"], r"^CERT-\d{8}-[0-9A-F]{8}$")

    def test_instructor_sees_their_students_certificates(self):
        """Test instructor sees certificates for their students"""
        cert_number = _make_certificate_number()
        EarnedCertificate.objects.create(
            enrollment=self.enrollment,
            template=self.template,
            certificate_number=cert_number,
            rendered_content=_render_content(self.template, self.enrollment),
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("earned-certificate-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        result = response.data["results"][0]
        self.assertEqual(result["certificate_number"], cert_number)
        self.assertRegex(result["certificate_number"], r"^CERT-\d{8}-[0-9A-F]{8}$")

    def test_student_cannot_see_others_certificates(self):
        """Test student cannot see other student's certificates"""
        other_student = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        EarnedCertificate.objects.create(
            enrollment=self.enrollment,
            template=self.template,
            certificate_number=_make_certificate_number(),
            rendered_content=_render_content(self.template, self.enrollment),
        )
        self.client.force_authenticate(user=other_student)
        response = self.client.get(reverse("earned-certificate-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_revoke_certificate(self):
        """Test revoking a certificate"""
        certificate = EarnedCertificate.objects.create(
            enrollment=self.enrollment,
            template=self.template,
            certificate_number=_make_certificate_number(),
            rendered_content=_render_content(self.template, self.enrollment),
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("earned-certificate-revoke", args=[certificate.id]),
            {"reason": "Academic integrity violation"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_revoked"])
        self.assertIsNotNone(response.data["revoked_at"])

    def test_cannot_revoke_twice(self):
        """Test cannot revoke already revoked certificate"""
        certificate = EarnedCertificate.objects.create(
            enrollment=self.enrollment,
            template=self.template,
            certificate_number=_make_certificate_number(),
            rendered_content=_render_content(self.template, self.enrollment),
            is_revoked=True,
            revoked_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("earned-certificate-revoke", args=[certificate.id]),
            {"reason": "Mistake"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_certificate_number_unique(self):
        """Test certificate numbers are unique"""
        duplicate_number = _make_certificate_number()
        EarnedCertificate.objects.create(
            enrollment=self.enrollment,
            template=self.template,
            certificate_number=duplicate_number,
            rendered_content=_render_content(self.template, self.enrollment),
        )
        student2 = User.objects.create_user(
            email="student2@example.com",
            name="Student 2",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        enrollment2 = Enrollment.objects.create(
            student=student2,
            course=self.course,
        )
        with self.assertRaises(Exception):
            EarnedCertificate.objects.create(
                enrollment=enrollment2,
                template=self.template,
                certificate_number=duplicate_number,  # Same number — must raise
                rendered_content=_render_content(self.template, enrollment2),
            )

    def test_rendered_content_contains_student_name_and_course(self):
        """Certificate rendered_content must include student name and course title."""
        cert = EarnedCertificate.objects.create(
            enrollment=self.enrollment,
            template=self.template,
            certificate_number=_make_certificate_number(),
            rendered_content=_render_content(self.template, self.enrollment),
        )
        self.assertIn(
            self.student.name, cert.rendered_content,
            "Rendered certificate must contain the student's name",
        )
        self.assertIn(
            self.course.title, cert.rendered_content,
            "Rendered certificate must contain the course title",
        )
