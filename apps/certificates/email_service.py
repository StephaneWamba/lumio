"""Certificate email delivery via Resend with PDF attachment."""

import base64
import boto3
import resend
import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)


def send_certificate_email(
    student_email: str,
    student_name: str,
    course_title: str,
    certificate_number: str,
    pdf_s3_key: str,
) -> None:
    """
    Download the certificate PDF from S3 and email it to the student via Resend.
    """
    # Download PDF bytes from S3
    s3 = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    obj = s3.get_object(Bucket=settings.S3_ASSETS_BUCKET, Key=pdf_s3_key)
    pdf_bytes = obj["Body"].read()
    pdf_b64 = base64.b64encode(pdf_bytes).decode()

    resend.api_key = settings.RESEND_API_KEY

    params: resend.Emails.SendParams = {
        "from": "onboarding@resend.dev",
        "to": [student_email],
        "subject": f"Your Certificate for {course_title}",
        "html": f"""
<p>Congratulations, {student_name}!</p>
<p>
  You have successfully completed <strong>{course_title}</strong>.
  Your certificate is attached to this email.
</p>
<p>Certificate number: <strong>{certificate_number}</strong></p>
<p>Well done — keep learning!</p>
<p>The Lumio Team</p>
""",
        "attachments": [
            {
                "filename": f"{certificate_number}.pdf",
                "content": pdf_b64,
            }
        ],
    }

    response = resend.Emails.send(params)
    logger.info(
        "certificate_email_sent",
        student_email=student_email,
        certificate_number=certificate_number,
        email_id=response.get("id"),
    )
