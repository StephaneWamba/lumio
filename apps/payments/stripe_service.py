"""Stripe API wrapper — PaymentIntents, Connect, Refunds, Webhooks."""

import stripe
import structlog
from django.conf import settings

logger = structlog.get_logger(__name__)


def _client():
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def create_payment_intent(
    amount_decimal,
    currency: str,
    metadata: dict,
    idempotency_key: str,
    instructor_stripe_id: str | None = None,
) -> stripe.PaymentIntent:
    """
    Create a Stripe PaymentIntent.
    amount_decimal: Decimal in currency units (e.g. 49.99).
    Returns the PaymentIntent object (contains client_secret for frontend).
    """
    s = _client()
    amount_cents = int(amount_decimal * 100)
    platform_fee = int(amount_cents * settings.STRIPE_PLATFORM_SHARE_PCT / 100)

    kwargs: dict = {
        "amount": amount_cents,
        "currency": currency.lower(),
        "metadata": metadata,
        "automatic_payment_methods": {"enabled": True},
    }
    if instructor_stripe_id:
        kwargs["application_fee_amount"] = platform_fee
        kwargs["transfer_data"] = {"destination": instructor_stripe_id}

    intent = s.PaymentIntent.create(**kwargs, idempotency_key=idempotency_key)
    logger.info(
        "stripe_payment_intent_created",
        intent_id=intent.id,
        amount_cents=amount_cents,
    )
    return intent


def create_refund(payment_intent_id: str, amount_cents: int | None = None) -> stripe.Refund:
    """Refund a PaymentIntent, optionally partial."""
    s = _client()
    kwargs: dict = {"payment_intent": payment_intent_id}
    if amount_cents is not None:
        kwargs["amount"] = amount_cents

    refund = s.Refund.create(**kwargs)
    logger.info("stripe_refund_created", refund_id=refund.id, payment_intent_id=payment_intent_id)
    return refund


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    """Verify and parse a Stripe webhook payload."""
    s = _client()
    return s.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)


def create_connect_account() -> stripe.Account:
    """Create a Stripe Express Connect account for an instructor."""
    s = _client()
    account = s.Account.create(type="express")
    logger.info("stripe_connect_account_created", account_id=account.id)
    return account


def create_account_link(account_id: str, refresh_url: str, return_url: str) -> stripe.AccountLink:
    """Generate an onboarding link for a Connect Express account."""
    s = _client()
    return s.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )
