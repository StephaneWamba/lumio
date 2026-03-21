"""Celery tasks for certificates — completion detection and issuance."""

import uuid
import structlog
from celery import shared_task
from django.utils import timezone

from apps.enrollments.models import Enrollment
from .models import CertificateAward, CertificateTemplate, EarnedCertificate
from . import pdf_service, email_service

logger = structlog.get_logger(__name__)


@shared_task(name="certificates.check_completions")
def check_completions():
    """Every 15 min: issue certificates for newly completed enrollments.

    Idempotent: only processes enrollments with no existing EarnedCertificate.
    Requires both a CertificateAward and CertificateTemplate on the course.
    """
    completed = Enrollment.objects.filter(
        progress_percentage=100,
        earned_certificate__isnull=True,
    ).select_related("student", "course").prefetch_related(
        "course__certificate_award",
        "course__certificate_template",
    )

    checked = 0
    issued = 0

    for enrollment in completed:
        checked += 1

        try:
            award = enrollment.course.certificate_award
        except CertificateAward.DoesNotExist:
            continue

        if not award.check_eligibility(enrollment):
            continue

        try:
            template = enrollment.course.certificate_template
        except CertificateTemplate.DoesNotExist:
            continue

        certificate_number = (
            f"CERT-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        )
        completion_date = timezone.now().strftime("%B %d, %Y")
        rendered_content = template.content.format(
            student_name=enrollment.student.name,
            course_title=enrollment.course.title,
            completion_date=completion_date,
        )

        pdf_s3_key = pdf_service.render_and_upload(
            certificate_number=certificate_number,
            student_name=enrollment.student.name,
            course_title=enrollment.course.title,
            completion_date=completion_date,
            template=template,
        )

        EarnedCertificate.objects.create(
            enrollment=enrollment,
            template=template,
            certificate_number=certificate_number,
            rendered_content=rendered_content,
            pdf_s3_key=pdf_s3_key,
        )

        email_service.send_certificate_email(
            student_email=enrollment.student.email,
            student_name=enrollment.student.name,
            course_title=enrollment.course.title,
            certificate_number=certificate_number,
            pdf_s3_key=pdf_s3_key,
        )

        issued += 1
        logger.info(
            "certificate_issued",
            enrollment_id=enrollment.id,
            student_id=enrollment.student.id,
            course_id=enrollment.course.id,
            certificate_number=certificate_number,
            pdf_s3_key=pdf_s3_key,
        )

    return {"checked": checked, "issued": issued}
