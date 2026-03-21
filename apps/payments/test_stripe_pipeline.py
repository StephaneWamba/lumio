"""Stripe pipeline integration tests — hits real Stripe test mode."""

from decimal import Decimal

from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from apps.users.models import InstructorProfile, User

from .models import Invoice, Payment, PaymentLog, Price
from .views import StripeWebhookView


def _skip_if_no_stripe():
    return not bool(settings.STRIPE_SECRET_KEY)


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
        """Returns a genuine Stripe client_secret starting with pi_."""
        if _skip_if_no_stripe():
            self.skipTest("STRIPE_SECRET_KEY not configured")

        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("payment-initiate-payment"),
            {"course_id": self.course.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("client_secret", response.data)
        self.assertTrue(response.data["client_secret"].startswith("pi_"))
        self.assertTrue(response.data["transaction_id"].startswith("pi_"))

    def test_initiate_payment_idempotent(self):
        """Calling initiate_payment twice returns the same PaymentIntent."""
        if _skip_if_no_stripe():
            self.skipTest("STRIPE_SECRET_KEY not configured")

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
        self.assertEqual(Payment.objects.filter(user=self.student, course=self.course).count(), 1)


class StripeWebhookTests(TestCase):
    """Webhook handler correctly updates payment state and creates enrollments."""

    def setUp(self):
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
            transaction_id="pi_test_webhook_001",
            status=Payment.STATUS_PENDING,
        )

    def _make_intent_obj(self, intent_id, extra=None):
        obj = {
            "id": intent_id,
            "metadata": {"payment_id": str(self.payment.id)},
        }
        if extra:
            obj.update(extra)
        return obj

    def test_webhook_payment_succeeded_marks_completed(self):
        """payment_intent.succeeded marks payment COMPLETED and creates Invoice + Enrollment."""
        view = StripeWebhookView()
        view._handle_payment_succeeded(self._make_intent_obj("pi_test_webhook_001"))

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_COMPLETED)
        self.assertIsNotNone(self.payment.completed_at)
        self.assertTrue(Invoice.objects.filter(payment=self.payment).exists())
        self.assertTrue(
            Enrollment.objects.filter(student=self.student, course=self.course).exists()
        )

    def test_webhook_payment_succeeded_idempotent(self):
        """Calling handler twice does not create duplicate invoices or enrollments."""
        view = StripeWebhookView()
        obj = self._make_intent_obj("pi_test_webhook_001")
        view._handle_payment_succeeded(obj)
        view._handle_payment_succeeded(obj)

        self.assertEqual(Invoice.objects.filter(payment=self.payment).count(), 1)
        self.assertEqual(
            Enrollment.objects.filter(student=self.student, course=self.course).count(), 1
        )

    def test_webhook_payment_failed_marks_failed(self):
        """payment_intent.payment_failed marks payment FAILED."""
        view = StripeWebhookView()
        obj = self._make_intent_obj(
            "pi_test_webhook_001",
            {"last_payment_error": {"message": "Card declined"}},
        )
        view._handle_payment_failed(obj)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_FAILED)
        self.assertEqual(self.payment.processor_response, "Card declined")

    def test_webhook_charge_refunded_marks_refunded(self):
        """charge.refunded marks payment REFUNDED via intent lookup."""
        self.payment.status = Payment.STATUS_COMPLETED
        self.payment.save()

        view = StripeWebhookView()
        charge = {
            "payment_intent": "pi_test_webhook_001",
            "amount_refunded": 999,  # cents
        }
        view._handle_charge_refunded(charge)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.STATUS_REFUNDED)
        self.assertTrue(self.payment.is_refunded)
        self.assertEqual(self.payment.refunded_amount, Decimal("9.99"))

    def test_webhook_unknown_payment_id_is_ignored(self):
        """Handler with no matching payment_id does not crash."""
        view = StripeWebhookView()
        view._handle_payment_succeeded(
            {"id": "pi_x", "metadata": {"payment_id": "99999"}}
        )
        # No exception = pass


class StripeRefundTests(TestCase):
    """Real Stripe refund via the refund action."""

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

    def test_refund_real_stripe_payment(self):
        """
        Full flow: create PaymentIntent → simulate confirmation via webhook → refund.
        Uses real Stripe test mode.
        """
        if _skip_if_no_stripe():
            self.skipTest("STRIPE_SECRET_KEY not configured")

        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY

        # Create and confirm a PaymentIntent in test mode using a test payment method
        Price.objects.create(course=self.course, amount=Decimal("5.00"), currency="USD")
        self.client.force_authenticate(user=self.student)
        r = self.client.post(
            reverse("payment-initiate-payment"), {"course_id": self.course.id}
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        intent_id = r.data["transaction_id"]
        payment = Payment.objects.get(transaction_id=intent_id)

        # Confirm with test card pm_card_visa (bypasses 3DS)
        stripe.PaymentIntent.confirm(
            intent_id,
            payment_method="pm_card_visa",
            return_url="https://lumio.io/return",
        )

        # Simulate webhook: mark payment completed
        view = StripeWebhookView()
        view._handle_payment_succeeded(
            {"id": intent_id, "metadata": {"payment_id": str(payment.id)}}
        )
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_COMPLETED)

        # Now refund via API
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("payment-refund", args=[payment.id]),
            {"reason": "Test refund"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_refunded"])


class StripeConnectOnboardingTests(TestCase):
    """Stripe Connect Express account creation."""

    def setUp(self):
        self.client: APIClient = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@connect-test.com",
            name="Connect Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        InstructorProfile.objects.create(user=self.instructor)

    def test_onboard_stripe_creates_account_and_returns_url(self):
        """Returns an onboarding_url pointing to Stripe Express onboarding."""
        if _skip_if_no_stripe():
            self.skipTest("STRIPE_SECRET_KEY not configured")

        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(reverse("instructorprofile-onboard-stripe"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("onboarding_url", response.data)
        self.assertTrue(response.data["onboarding_url"].startswith("https://connect.stripe.com/"))

        # Stripe account ID persisted
        self.instructor.instructor_profile.refresh_from_db()
        self.assertTrue(
            self.instructor.instructor_profile.stripe_account_id.startswith("acct_")
        )
