"""Shared Resend email helper used by all apps."""

import resend
import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)


def send_transactional_email(to: str, subject: str, html: str) -> str:
    """
    Send a transactional email via Resend.
    Returns the Resend message ID.
    Raises on delivery failure (let the caller decide retry strategy).
    """
    resend.api_key = settings.RESEND_API_KEY

    params = resend.Emails.SendParams(
        from_="onboarding@resend.dev",
        to=[to],
        subject=subject,
        html=html,
    )

    response = resend.Emails.send(params)
    email_id = response.get("id") if isinstance(response, dict) else getattr(response, "id", None)

    logger.info(
        "transactional_email_sent",
        to=to,
        subject=subject,
        email_id=email_id,
    )
    return email_id
