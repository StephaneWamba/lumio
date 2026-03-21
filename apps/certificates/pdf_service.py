"""Certificate PDF generation: WeasyPrint → PDF bytes → S3 upload."""

import boto3
import structlog
from django.conf import settings
from weasyprint import HTML

logger = structlog.get_logger(__name__)

_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    @page {{
      size: A4 landscape;
      margin: 2cm;
    }}
    body {{
      font-family: Georgia, "Times New Roman", serif;
      background: #fff;
      color: #222;
      text-align: center;
    }}
    .border {{
      border: 8px solid {color_primary};
      border-radius: 8px;
      padding: 40px 60px;
      min-height: 520px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
    }}
    .institution {{
      font-size: 14px;
      letter-spacing: 3px;
      text-transform: uppercase;
      color: {color_accent};
      margin-bottom: 24px;
    }}
    .title {{
      font-size: 36px;
      color: {color_primary};
      margin-bottom: 16px;
      font-weight: bold;
    }}
    .body {{
      font-size: 18px;
      line-height: 1.8;
      max-width: 680px;
      margin: 0 auto 32px;
    }}
    .student-name {{
      font-size: 28px;
      color: {color_primary};
      font-style: italic;
      border-bottom: 2px solid {color_accent};
      padding-bottom: 4px;
      display: inline-block;
      margin: 8px 0;
    }}
    .cert-number {{
      font-size: 11px;
      color: #888;
      margin-top: 32px;
      letter-spacing: 1px;
    }}
    .signature {{
      font-size: 14px;
      margin-top: 48px;
      border-top: 1px solid #ccc;
      padding-top: 8px;
      display: inline-block;
      min-width: 200px;
    }}
    .date {{
      font-size: 14px;
      color: #555;
      margin-top: 12px;
    }}
  </style>
</head>
<body>
  <div class="border">
    <div class="institution">{institution_name}</div>
    <div class="title">{cert_title}</div>
    <div class="body">
      This certifies that<br>
      <span class="student-name">{student_name}</span><br>
      has successfully completed<br>
      <strong>{course_title}</strong>
    </div>
    <div class="date">{completion_date}</div>
    {signature_html}
    <div class="cert-number">Certificate No. {certificate_number}</div>
  </div>
</body>
</html>
"""


def render_and_upload(
    certificate_number: str,
    student_name: str,
    course_title: str,
    completion_date: str,
    template,
) -> str:
    """
    Render a certificate as PDF via WeasyPrint and upload to S3 assets bucket.
    Returns the S3 key of the uploaded PDF.
    """
    signature_html = (
        f'<div class="signature">{template.signature_text}</div>'
        if template.signature_text
        else ""
    )

    html_content = _HTML_TEMPLATE.format(
        color_primary=template.color_primary or "#003366",
        color_accent=template.color_accent or "#0099CC",
        institution_name=template.institution_name or "Lumio Learning",
        cert_title=template.title,
        student_name=student_name,
        course_title=course_title,
        completion_date=completion_date,
        signature_html=signature_html,
        certificate_number=certificate_number,
    )

    pdf_bytes = HTML(string=html_content).write_pdf()

    s3_key = f"certificates/{certificate_number}.pdf"
    s3 = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    s3.put_object(
        Bucket=settings.S3_ASSETS_BUCKET,
        Key=s3_key,
        Body=pdf_bytes,
        ContentType="application/pdf",
        ContentDisposition=f'attachment; filename="{certificate_number}.pdf"',
    )

    logger.info(
        "certificate_pdf_uploaded",
        certificate_number=certificate_number,
        s3_key=s3_key,
        size_bytes=len(pdf_bytes),
    )
    return s3_key


def generate_download_url(s3_key: str, expiry_seconds: int = 3600) -> str:
    """Generate a presigned S3 URL to download the certificate PDF."""
    s3 = boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_ASSETS_BUCKET, "Key": s3_key},
        ExpiresIn=expiry_seconds,
    )
