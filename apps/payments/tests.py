"""Tests for payments"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

from apps.users.models import User
from apps.courses.models import Course
from .models import Price, Payment, Invoice


class PriceTests(TestCase):
    """Test course pricing"""

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

    def test_create_price(self):
        """Test creating price for a course"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("price-list"),
            {
                "course_id": self.course.id,
                "amount": "99.99",
                "currency": "USD",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["amount"], "99.99")

    def test_discounted_amount_calculation(self):
        """Test discounted amount calculation"""
        price = Price.objects.create(
            course=self.course,
            amount=Decimal("100.00"),
            currency="USD",
            discount_percent=Decimal("20"),
            discount_until=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(price.discounted_amount, Decimal("80.00"))

    def test_inactive_discount(self):
        """Test inactive discount returns original amount"""
        price = Price.objects.create(
            course=self.course,
            amount=Decimal("100.00"),
            currency="USD",
            discount_percent=Decimal("20"),
            discount_until=timezone.now() - timedelta(days=1),  # Expired
        )
        self.assertEqual(price.discounted_amount, Decimal("100.00"))

    def test_list_prices(self):
        """Test listing prices"""
        Price.objects.create(
            course=self.course,
            amount=Decimal("99.99"),
            currency="USD",
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("price-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_cannot_create_price_for_others_course(self):
        """Test cannot create price for other's course"""
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
            reverse("price-list"),
            {
                "course_id": other_course.id,
                "amount": "99.99",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class PaymentTests(TestCase):
    """Test payments"""

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
            email="student@example.com",
            name="Test Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Test Course",
            is_published=True,
        )
        self.price = Price.objects.create(
            course=self.course,
            amount=Decimal("99.99"),
            currency="USD",
        )

    def test_list_payments_requires_auth(self):
        """Test listing payments requires auth"""
        response = self.client.get(reverse("payment-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_sees_own_payments(self):
        """Test student sees only their own payments"""
        Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal("99.99"),
            currency="USD",
            transaction_id="TXN-001",
        )
        other_student = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        Payment.objects.create(
            user=other_student,
            course=self.course,
            amount=Decimal("99.99"),
            currency="USD",
            transaction_id="TXN-002",
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("payment-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_initiate_payment_creates_stripe_intent(self):
        """Initiating a payment calls real Stripe and returns a client_secret."""
        import django.conf as conf
        if not conf.settings.STRIPE_SECRET_KEY:
            self.skipTest("STRIPE_SECRET_KEY not configured")

        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("payment-initiate-payment"),
            {"course_id": self.course.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["amount"], "99.99")
        self.assertIn("client_secret", response.data)
        self.assertTrue(response.data["client_secret"].startswith("pi_"))

    def test_initiate_payment_without_pricing(self):
        """Test cannot initiate payment for course without pricing"""
        unpri_course = Course.objects.create(
            instructor=self.instructor,
            title="Unpaid Course",
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("payment-initiate-payment"),
            {"course_id": unpri_course.id},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mark_payment_failed(self):
        """Test marking payment as failed"""
        payment = Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal("99.99"),
            currency="USD",
            transaction_id="TXN-TEST-002",
            status=Payment.STATUS_PENDING,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.post(
            reverse("payment-mark-failed", args=[payment.id]),
            {"error_message": "Card declined"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "failed")

    def test_refund_requires_completed_status(self):
        """Refunding a pending payment returns 400."""
        payment = Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal("99.99"),
            currency="USD",
            transaction_id="pi-fake-pending",
            status=Payment.STATUS_PENDING,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("payment-refund", args=[payment.id]),
            {"reason": "Mistake"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_refund_non_completed(self):
        """Test cannot refund non-completed payment"""
        payment = Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal("99.99"),
            currency="USD",
            transaction_id="TXN-TEST-004",
            status=Payment.STATUS_PENDING,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("payment-refund", args=[payment.id]),
            {"reason": "Mistake"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_instructor_sees_student_payments(self):
        """Test instructor sees student payments for their courses"""
        Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal("99.99"),
            currency="USD",
            transaction_id="TXN-005",
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("payment-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)


class InvoiceTests(TestCase):
    """Test invoices"""

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
            email="student@example.com",
            name="Test Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Test Course",
        )
        self.payment = Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal("99.99"),
            currency="USD",
            transaction_id="TXN-INV-001",
            status=Payment.STATUS_COMPLETED,
        )

    def test_list_invoices_requires_auth(self):
        """Test listing invoices requires auth"""
        response = self.client.get(reverse("invoice-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_student_sees_own_invoices(self):
        """Test student sees own invoices"""
        Invoice.objects.create(
            payment=self.payment,
            invoice_number="INV-001",
            status=Invoice.STATUS_ISSUED,
            subtotal=Decimal("99.99"),
            total_amount=Decimal("99.99"),
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("invoice-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_webhook_payment_succeeded_creates_invoice_and_enrollment(self):
        """Stripe webhook payment_intent.succeeded → invoice + enrollment created."""
        import json
        import stripe
        from django.conf import settings
        from apps.enrollments.models import Enrollment

        payment = Payment.objects.create(
            user=self.student,
            course=self.course,
            amount=Decimal("49.99"),
            currency="USD",
            transaction_id="pi_test_webhook_001",
            status=Payment.STATUS_PENDING,
        )

        # Build a minimal payment_intent.succeeded event payload
        payload = json.dumps({
            "id": "evt_test_001",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "id": "pi_test_webhook_001",
                    "metadata": {"payment_id": str(payment.id)},
                }
            },
        }).encode()

        # Sign it with the real webhook secret so our view accepts it
        stripe.api_key = settings.STRIPE_SECRET_KEY
        import time
        ts = int(time.time())
        signed_payload = f"{ts}.{payload.decode()}"
        import hmac, hashlib
        sig = hmac.new(
            settings.STRIPE_WEBHOOK_SECRET.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        stripe_sig = f"t={ts},v1={sig}"

        response = self.client.post(
            reverse("stripe-webhook"),
            data=payload,
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE=stripe_sig,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.STATUS_COMPLETED)
        self.assertTrue(Invoice.objects.filter(payment=payment).exists())
        self.assertTrue(Enrollment.objects.filter(student=self.student, course=self.course).exists())
