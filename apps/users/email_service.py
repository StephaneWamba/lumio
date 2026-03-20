"""Resend email delivery for auth flows."""

import resend
import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)

FROM_EMAIL = "onboarding@resend.dev"


def _get_frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "https://lumio.io")


def send_verification_email(user_email: str, user_name: str, token: str) -> None:
    """Send email verification link to the user."""
    resend.api_key = settings.RESEND_API_KEY
    verify_url = f"{_get_frontend_url()}/verify-email?token={token}"

    try:
        resend.Emails.send(
            {
                "from": FROM_EMAIL,
                "to": [user_email],
                "subject": "Verify your Lumio email",
                "html": (
                    f"<p>Hi {user_name},</p>"
                    f"<p>Please verify your email by clicking the link below:</p>"
                    f"<p><a href='{verify_url}'>Verify Email</a></p>"
                    f"<p>This link expires in 24 hours.</p>"
                ),
            }
        )
        logger.info("verification_email_sent", email=user_email)
    except Exception as exc:
        logger.error("verification_email_failed", email=user_email, error=str(exc))
        raise


def send_password_reset_email(user_email: str, user_name: str, token: str) -> None:
    """Send password reset link to the user."""
    resend.api_key = settings.RESEND_API_KEY
    reset_url = f"{_get_frontend_url()}/reset-password?token={token}"

    try:
        resend.Emails.send(
            {
                "from": FROM_EMAIL,
                "to": [user_email],
                "subject": "Reset your Lumio password",
                "html": (
                    f"<p>Hi {user_name},</p>"
                    f"<p>Click the link below to reset your password:</p>"
                    f"<p><a href='{reset_url}'>Reset Password</a></p>"
                    f"<p>This link expires in 1 hour. If you did not request this, ignore this email.</p>"
                ),
            }
        )
        logger.info("password_reset_email_sent", email=user_email)
    except Exception as exc:
        logger.error("password_reset_email_failed", email=user_email, error=str(exc))
        raise
