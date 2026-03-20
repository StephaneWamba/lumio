"""S3 presigned upload + CloudFront signed URL service for video pipeline."""

import base64
import uuid
from datetime import datetime, timedelta, timezone

import boto3
import structlog
from botocore.signers import CloudFrontSigner
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from django.conf import settings

logger = structlog.get_logger(__name__)

# Signed URL validity
SIGNED_URL_TTL_SECONDS = 300  # 5 minutes


def _get_s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def generate_presigned_upload_url(lesson_id: int, file_name: str, file_size_bytes: int) -> dict:
    """
    Generate a presigned S3 PUT URL so the frontend uploads directly.
    Returns: {upload_url, s3_key, expires_in}
    """
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else "mp4"
    s3_key = f"raw/{lesson_id}/{uuid.uuid4().hex}.{ext}"

    s3 = _get_s3_client()
    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.S3_RAW_BUCKET,
            "Key": s3_key,
            "ContentType": "video/mp4",
            "ContentLength": file_size_bytes,
        },
        ExpiresIn=3600,  # 1 hour to complete the upload
    )

    logger.info("presigned_upload_url_generated", lesson_id=lesson_id, s3_key=s3_key)
    return {"upload_url": upload_url, "s3_key": s3_key, "expires_in": 3600}


def _rsa_signer(message: bytes) -> bytes:
    """Sign message with CloudFront private key (RSA-SHA1 as required by CloudFront)."""
    private_key_b64 = settings.CLOUDFRONT_PRIVATE_KEY_B64
    private_key_pem = base64.b64decode(private_key_b64)
    private_key = serialization.load_pem_private_key(private_key_pem, password=None)
    return private_key.sign(message, padding.PKCS1v15(), hashes.SHA1())  # noqa: S303


def generate_cloudfront_signed_url(s3_key: str) -> tuple[str, datetime]:
    """
    Generate a CloudFront signed URL for a processed media key.
    Returns: (signed_url, expires_at)
    """
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=SIGNED_URL_TTL_SECONDS)
    cloudfront_domain = settings.CLOUDFRONT_DOMAIN
    key_pair_id = settings.CLOUDFRONT_KEY_PAIR_ID

    signer = CloudFrontSigner(key_pair_id, _rsa_signer)
    url = f"https://{cloudfront_domain}/{s3_key}"
    signed_url = signer.generate_presigned_url(url, date_less_than=expires_at)

    logger.info("cloudfront_signed_url_generated", s3_key=s3_key, expires_at=expires_at)
    return signed_url, expires_at
