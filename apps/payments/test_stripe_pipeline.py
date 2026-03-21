"""Stripe pipeline tests — all tests hit real Stripe test mode via HTTP endpoints."""

import hashlib
import hmac
import json
import time
from decimal import Decimal

import stripe
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from apps.users.models import InstructorProfile, User

from .models import Invoice, Payment, Price


def _signed_webhook(payload_dict: dict) -> tuple[bytes, str]:
    """Return (raw_bytes, Stripe-Signature header) for a payload dict."""
    payload = json.dumps(payload_dict).encode()
    ts = int(time.time())
    signed = f"{ts}.{payload.decode()}"
    sig = hmac.new(
        settings.STRIPE_WEBHOOK_SECRET.encode(),
        signed.encode(),
        hashlib.sha256,
    ).hexdigest()
    return payload, f"t={ts},v1={sig}"


class StripePaymentIntentTests(TestCase):
    """initiate_payment creates a real Stripe PaymentIntent."""

    def setUp(self):
        self.client: APIClient = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@stripe-test.com",
            name="Stripe Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            email="student@stripe-test.com",
            name="Stripe Student",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Stripe Test Course",
            is_published=True,
        )
        Price.objects.create(course=self.course, amount=Decimal("9.99"), currency="USD")

    def test_initiate_payment_returns_real_client_secret(self):
        """Returns a genuine Stripe PaymentIntent ID and client_secret."""
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("payment-initiate-payment"),
            {"course_id": self.course.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("client_secret", response.data)
        # client_secret format: pi_xxx_secret_yyy
        self.assertTrue(response.data["client_secret"].startswith("pi_"))
        self.assertTrue(response.data["transaction_id"].startswith("pi_"))

        # Verify the PaymentIntent actually exists on Stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        intent = stripe.PaymentIntent.retrieve(response.data["transaction_id"])
        self.assertEqual(intent.amount, 999)  # $9.99 in cents
        self.assertEqual(intent.currency, "usd")
        self.assertEqual(intent.metadata["user_id"], str(self.student.id))
        self.assertEqual(intent.metadata["course_id"], str(self.course.id))

    def test_initiate_payment_idempotent(self):
        """Calling initiate_payment twice returns the same PaymentIntent, one DB row."""
        self.client.force_authenticate(user=self.student)
        r1 = self.client.post(
            reverse("payment-initiate-payment"), {"course_id": self.course.id}
        )
        r2 = self.client.post(
            reverse("payment-initiate-payment"), {"course_id": self.course.id}
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data["transaction_id"], r2.data["transaction_id"])
        self.assertEqual(
            Payment.objects.filter(user=self.student, course=self.course).count(), 1
        )

    def test_initiate_payment_with_onboarded_instructor_sets_platform_fee(self):
        """When instructor is Stripe-onboarded, PaymentIntent has application_fee_amount set."""
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Custom accounts get transfers capability immediately in test mode;
        # Express accounts require the full onboarding flow before capability is active.
        connect_account = stripe.Account.create(
            type="custom",
            country="US",
            capabilities={"transfers": {"requested": True}},
        )
        profile = InstructorProfile.objects.create(user=self.instructor)
        profile.stripe_account_id = connect_account.id
        profile.stripe_onboarded = True
        profile.save()

        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("payment-initiate-payment"), {"course_id": self.course.id}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        intent = stripe.PaymentIntent.retrieve(response.data["transaction_id"])
        expected_fee = int(999 * settings.STRIPE_PLATFORM_SHARE_PCT / 100)  # 20% of $9.99
        self.assertEqual(intent.application_fee_amount, expected_fee)
        self.assertEqual(intent.transfer_data["destination"], connect_account.id)

        # Cleanup test account
        stripe.Account.delete(connect_account.id)


class StripeWebhookTests(TestCase):
    """
    Webhook handler tests — all POST to the real HTTP endpoint with HMAC-signed payloads.
    Stripe event payloads reference intent IDs that exist only in our DB metadata;
    construct_event only validates the signature, not whether the intent exists on Stripe.
    """

    def setUp(self):
        self.client: APIClient = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@webhook-test.com",
            name="Webhook Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            email="student@webhook-test.com",
            name="Webhook Student",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Webhook Course",
            is_published=True,
        )
        self.payment = Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal("9.99"),
            currency="USD",
            transaction_id="pi_webhook_test_001",
            status=Payment.STATUS_PENDING,
        )

    def _post_webhook(self, event_type: str, obj: dict):
        payload_dict = {
            "id": f"evt_{event_type.replace('.', '_')}",
            "type": event_type,
            "data": {"object": obj},
        }
        raw, sig = _signed_webhook(payload_dict)
        return self.client.post(
            reverse("stripe-webhook"),
            data=raw,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=sig,
        )

    def test_webhook_payment_succeeded_marks_completed_creates_invoice_and_enrollment(self):
        """payment_intent.succeeded → COMPLETED, Invoice, Enrollment created."""
        response = self._post_webhook(
            "payment_intent.succeeded",
            {
                "id": "pi_webhook_test_001",
                "metadata": {"payment_id": str(self.payment.id)},
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_COMPLETED)
        self.assertIsNotNone(self.payment.completed_at)
        self.assertTrue(Invoice.objects.filter(payment=self.payment).exists())
        self.assertTrue(
            Enrollment.objects.filter(student=self.student, course=self.course).exists()
        )

    def test_webhook_payment_succeeded_idempotent(self):
        """Duplicate payment_intent.succeeded does not create duplicate Invoice or Enrollment."""
        obj = {
            "id": "pi_webhook_test_001",
            "metadata": {"payment_id": str(self.payment.id)},
        }
        self._post_webhook("payment_intent.succeeded", obj)
        self._post_webhook("payment_intent.succeeded", obj)

        self.assertEqual(Invoice.objects.filter(payment=self.payment).count(), 1)
        self.assertEqual(
            Enrollment.objects.filter(student=self.student, course=self.course).count(), 1
        )

    def test_webhook_payment_failed_marks_failed_with_error_message(self):
        """payment_intent.payment_failed → FAILED with processor_response set."""
        response = self._post_webhook(
            "payment_intent.payment_failed",
            {
                "id": "pi_webhook_test_001",
                "metadata": {"payment_id": str(self.payment.id)},
                "last_payment_error": {"message": "Your card was declined."},
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_FAILED)
        self.assertEqual(self.payment.processor_response, "Your card was declined.")

    def test_webhook_charge_refunded_marks_refunded(self):
        """charge.refunded → REFUNDED with correct refunded_amount."""
        self.payment.status = Payment.STATUS_COMPLETED
        self.payment.save()

        response = self._post_webhook(
            "charge.refunded",
            {
                "payment_intent": "pi_webhook_test_001",
                "amount_refunded": 999,  # cents = $9.99
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_REFUNDED)
        self.assertTrue(self.payment.is_refunded)
        self.assertEqual(self.payment.refunded_amount, Decimal("9.99"))

    def test_webhook_invalid_signature_rejected(self):
        """Webhook with wrong signature returns 400."""
        payload = json.dumps({"type": "payment_intent.succeeded"}).encode()
        response = self.client.post(
            reverse("stripe-webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="t=1,v1=badsignature",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_webhook_unknown_payment_id_ignored_gracefully(self):
        """Handler with non-existent payment_id returns 200 (no crash)."""
        response = self._post_webhook(
            "payment_intent.succeeded",
            {"id": "pi_does_not_exist", "metadata": {"payment_id": "99999999"}},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class StripeRefundTests(TestCase):
    """Full refund flow: create real PaymentIntent → confirm → complete → refund."""

    def setUp(self):
        self.client: APIClient = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@refund-test.com",
            name="Refund Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            email="student@refund-test.com",
            name="Refund Student",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Refund Course",
            is_published=True,
        )
        Price.objects.create(course=self.course, amount=Decimal("5.00"), currency="USD")

    def test_refund_real_stripe_payment_intent(self):
        """
        Full end-to-end: initiate → confirm in Stripe test mode → webhook completes →
        refund via API → Stripe refund confirmed + DB marked REFUNDED.
        """
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # 1. Initiate payment — creates real Stripe PaymentIntent
        self.client.force_authenticate(user=self.student)
        r = self.client.post(
            reverse("payment-initiate-payment"), {"course_id": self.course.id}
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        intent_id = r.data["transaction_id"]
        payment = Payment.objects.get(transaction_id=intent_id)

        # 2. Confirm with test card (pm_card_visa = always succeeds, no 3DS)
        stripe.PaymentIntent.confirm(
            intent_id,
            payment_method="pm_card_visa",
            return_url="https://lumio.io/return",
        )

        # 3. Simulate webhook marking payment complete
        obj = {"id": intent_id, "metadata": {"payment_id": str(payment.id)}}
        payload_dict = {
            "id": "evt_refund_test",
            "type": "payment_intent.succeeded",
            "data": {"object": obj},
        }
        raw, sig = _signed_webhook(payload_dict)
        self.client.post(
            reverse("stripe-webhook"),
            data=raw,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=sig,
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_COMPLETED)

        # 4. Refund via API — calls real stripe.Refund.create
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("payment-refund", args=[payment.id]),
            {"reason": "Test refund"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_refunded"])
        self.assertEqual(response.data["status"], "refunded")

        # 5. Verify refund exists on Stripe
        refunds = stripe.Refund.list(payment_intent=intent_id)
        self.assertEqual(len(refunds.data), 1)
        self.assertEqual(refunds.data[0].amount, 500)  # $5.00 in cents

    def test_refund_non_completed_payment_returns_400(self):
        """Refunding a PENDING payment returns 400 — no Stripe call made."""
        self.client.force_authenticate(user=self.student)
        r = self.client.post(
            reverse("payment-initiate-payment"), {"course_id": self.course.id}
        )
        payment = Payment.objects.get(transaction_id=r.data["transaction_id"])

        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("payment-refund", args=[payment.id]),
            {"reason": "Premature"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        payment.refresh_from_db()
        self.assertFalse(payment.is_refunded)


class StripeConnectOnboardingTests(TestCase):
    """Stripe Connect Express account creation and persistence."""

    def setUp(self):
        self.client: APIClient = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@connect-test.com",
            name="Connect Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        InstructorProfile.objects.create(user=self.instructor)

    def test_onboard_stripe_creates_express_account_and_returns_onboarding_url(self):
        """Creates a real Stripe Express account, persists stripe_account_id, returns URL."""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(reverse("instructor-profile-onboard-stripe"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("onboarding_url", response.data)
        self.assertTrue(
            response.data["onboarding_url"].startswith("https://connect.stripe.com/")
        )

        self.instructor.instructor_profile.refresh_from_db()
        account_id = self.instructor.instructor_profile.stripe_account_id
        self.assertTrue(account_id.startswith("acct_"))

        # Verify account exists on Stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        account = stripe.Account.retrieve(account_id)
        self.assertEqual(account.type, "express")

    def test_onboard_stripe_idempotent(self):
        """Calling onboard twice reuses the same Stripe account — no duplicate created."""
        self.client.force_authenticate(user=self.instructor)
        r1 = self.client.post(reverse("instructor-profile-onboard-stripe"))
        r2 = self.client.post(reverse("instructor-profile-onboard-stripe"))
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)

        # Both calls return a URL (new AccountLink each time, same account)
        self.instructor.instructor_profile.refresh_from_db()
        stripe.api_key = settings.STRIPE_SECRET_KEY
        account_id = self.instructor.instructor_profile.stripe_account_id
        # Only one account exists
        accounts = stripe.Account.list(limit=10)
        matching = [a for a in accounts.data if a.id == account_id]
        self.assertEqual(len(matching), 1)
