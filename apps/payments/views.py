"""Payments app views"""

import uuid
from decimal import Decimal

import structlog
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course
from apps.enrollments.models import Enrollment

from . import stripe_service
from .models import Invoice, Payment, PaymentLog, Price
from .serializers import (
    InvoiceDetailSerializer,
    InvoiceListSerializer,
    PaymentDetailSerializer,
    PaymentListSerializer,
    PriceSerializer,
)

logger = structlog.get_logger(__name__)


class PriceViewSet(viewsets.ModelViewSet):
    """ViewSet for course pricing"""

    queryset = Price.objects.all()
    serializer_class = PriceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return Price.objects.all()
        if user.role == "instructor":
            return Price.objects.filter(course__instructor=user)
        return Price.objects.filter(is_active=True)

    def perform_create(self, serializer):
        course = get_object_or_404(Course, id=self.request.data.get("course_id"))
        if self.request.user != course.instructor and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save()

    def perform_update(self, serializer):
        course = serializer.instance.course
        if self.request.user != course.instructor and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save()


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for payments"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return Payment.objects.all().select_related("user", "course")
        if user.role == "instructor":
            return Payment.objects.filter(course__instructor=user).select_related("user", "course")
        return Payment.objects.filter(user=user).select_related("user", "course")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return PaymentDetailSerializer
        return PaymentListSerializer

    @action(detail=False, methods=["post"])
    def initiate_payment(self, request):
        """
        Initiate a Stripe PaymentIntent for a course.
        Returns client_secret for frontend to confirm the payment.
        """
        course_id = request.data.get("course_id")
        if not course_id:
            return Response(
                {"detail": "course_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course = get_object_or_404(Course, id=course_id)

        if not hasattr(course, "pricing"):
            return Response(
                {"detail": "Course does not have pricing configured"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        price = course.pricing
        amount = price.discounted_amount if price.is_discount_active else price.amount

        # Idempotency: one payment per user+course in pending state
        existing = Payment.objects.filter(
            user=request.user,
            course=course,
            status=Payment.STATUS_PENDING,
        ).first()
        if existing:
            serializer = PaymentDetailSerializer(existing)
            data = serializer.data
            # Re-fetch intent's client_secret so frontend can retry
            intent = stripe_service._client().PaymentIntent.retrieve(existing.transaction_id)
            data["client_secret"] = intent.client_secret
            return Response(data, status=status.HTTP_200_OK)

        # Resolve instructor's Stripe account (if onboarded)
        instructor_stripe_id = None
        try:
            profile = course.instructor.instructor_profile
            if profile.stripe_onboarded and profile.stripe_account_id:
                instructor_stripe_id = profile.stripe_account_id
        except Exception:
            pass

        # Deterministic idempotency key: same user+course always yields same key
        idempotency_key = f"pi-{request.user.id}-{course.id}"

        intent = stripe_service.create_payment_intent(
            amount_decimal=amount,
            currency=price.currency,
            metadata={
                "course_id": str(course.id),
                "user_id": str(request.user.id),
            },
            idempotency_key=idempotency_key,
            instructor_stripe_id=instructor_stripe_id,
        )

        payment = Payment.objects.create(
            user=request.user,
            course=course,
            amount=amount,
            currency=price.currency,
            payment_method=Payment.PAYMENT_METHOD_CREDIT_CARD,
            transaction_id=intent.id,  # pi_xxx — used for refunds + webhook lookup
            status=Payment.STATUS_PENDING,
        )

        # Update metadata with our DB payment_id so webhook can look it up
        stripe_service._client().PaymentIntent.modify(
            intent.id,
            metadata={
                "payment_id": str(payment.id),
                "course_id": str(course.id),
                "user_id": str(request.user.id),
            },
        )

        PaymentLog.objects.create(
            payment=payment,
            log_type=PaymentLog.LOG_TYPE_CREATED,
            message=f"PaymentIntent created for {course.title}",
            details=intent.id,
        )

        serializer = PaymentDetailSerializer(payment)
        data = serializer.data
        data["client_secret"] = intent.client_secret
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        """Issue a real Stripe refund (admin or instructor only)."""
        payment = self.get_object()

        if payment.course.instructor != request.user and not request.user.is_staff:
            self.permission_denied(request)

        if payment.status != Payment.STATUS_COMPLETED:
            return Response(
                {"detail": "Payment is not completed"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if payment.is_refunded:
            return Response(
                {"detail": "Payment already refunded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refund_amount = Decimal(str(request.data.get("amount", payment.amount)))
        if refund_amount <= 0 or refund_amount > payment.amount:
            return Response(
                {"detail": f"Refund amount must be between 0.01 and {payment.amount}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        refund_cents = int(refund_amount * 100)

        stripe_service.create_refund(
            payment_intent_id=payment.transaction_id,
            amount_cents=refund_cents if refund_amount != payment.amount else None,
        )

        payment.is_refunded = True
        payment.refunded_amount = refund_amount
        payment.refunded_at = timezone.now()
        payment.refund_reason = request.data.get("reason", "")
        payment.status = Payment.STATUS_REFUNDED
        payment.save()

        PaymentLog.objects.create(
            payment=payment,
            log_type=PaymentLog.LOG_TYPE_REFUNDED,
            message=f"Refunded {refund_amount} {payment.currency}",
            details=payment.refund_reason,
        )

        return Response(PaymentDetailSerializer(payment).data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """
    Idempotent Stripe webhook handler.
    Handles: payment_intent.succeeded, payment_intent.payment_failed, charge.refunded
    """

    permission_classes = [AllowAny]

    def post(self, request):
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = stripe_service.construct_webhook_event(request.body, sig_header)
        except Exception as exc:
            logger.warning("stripe_webhook_invalid_signature", error=str(exc))
            return Response({"detail": "Invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        event_type = event["type"]
        obj = event["data"]["object"]

        if event_type == "payment_intent.succeeded":
            self._handle_payment_succeeded(obj)
        elif event_type == "payment_intent.payment_failed":
            self._handle_payment_failed(obj)
        elif event_type == "charge.refunded":
            self._handle_charge_refunded(obj)

        return Response({"status": "ok"}, status=status.HTTP_200_OK)

    def _handle_payment_succeeded(self, intent):
        payment_id = intent.get("metadata", {}).get("payment_id")
        if not payment_id:
            logger.warning("stripe_webhook_no_payment_id", intent_id=intent.get("id"))
            return

        with transaction.atomic():
            try:
                payment = Payment.objects.select_for_update().get(id=payment_id)
            except Payment.DoesNotExist:
                logger.warning("stripe_webhook_payment_not_found", payment_id=payment_id)
                return

            # Idempotent
            if payment.status == Payment.STATUS_COMPLETED:
                return

            payment.status = Payment.STATUS_COMPLETED
            payment.completed_at = timezone.now()
            payment.save(update_fields=["status", "completed_at"])

            # Create invoice
            invoice_number = (
                f"INV-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            )
            Invoice.objects.get_or_create(
                payment=payment,
                defaults={
                    "invoice_number": invoice_number,
                    "status": Invoice.STATUS_PAID,
                    "subtotal": payment.amount,
                    "tax_amount": Decimal("0.00"),
                    "total_amount": payment.amount,
                    "issued_date": timezone.now().date(),
                    "paid_date": timezone.now().date(),
                },
            )

            # Auto-enroll student
            Enrollment.objects.get_or_create(
                student=payment.user,
                course=payment.course,
            )

        PaymentLog.objects.create(
            payment=payment,
            log_type=PaymentLog.LOG_TYPE_COMPLETED,
            message="Payment confirmed via Stripe webhook",
            details=intent.get("id", ""),
        )
        logger.info("payment_completed", payment_id=payment.id, intent_id=intent.get("id"))

    def _handle_payment_failed(self, intent):
        payment_id = intent.get("metadata", {}).get("payment_id")
        if not payment_id:
            return

        with transaction.atomic():
            try:
                payment = Payment.objects.select_for_update().get(id=payment_id)
            except Payment.DoesNotExist:
                return

            if payment.status == Payment.STATUS_FAILED:
                return

            error = intent.get("last_payment_error", {}) or {}
            payment.status = Payment.STATUS_FAILED
            payment.processor_response = error.get("message", "Payment failed")
            payment.save(update_fields=["status", "processor_response"])

        PaymentLog.objects.create(
            payment=payment,
            log_type=PaymentLog.LOG_TYPE_FAILED,
            message="Payment failed via Stripe webhook",
            details=payment.processor_response,
        )
        logger.info("payment_failed", payment_id=payment.id)

    def _handle_charge_refunded(self, charge):
        intent_id = charge.get("payment_intent")
        if not intent_id:
            return

        with transaction.atomic():
            try:
                payment = Payment.objects.select_for_update().get(transaction_id=intent_id)
            except Payment.DoesNotExist:
                return

            if payment.is_refunded:
                return

            refunded_cents = charge.get("amount_refunded", 0)
            payment.is_refunded = True
            payment.refunded_amount = Decimal(str(refunded_cents / 100))
            payment.refunded_at = timezone.now()
            payment.status = Payment.STATUS_REFUNDED
            payment.save(update_fields=["is_refunded", "refunded_amount", "refunded_at", "status"])

        PaymentLog.objects.create(
            payment=payment,
            log_type=PaymentLog.LOG_TYPE_REFUNDED,
            message="Refund confirmed via Stripe webhook",
            details=str(refunded_cents),
        )
        logger.info("payment_refunded_via_webhook", payment_id=payment.id)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for invoices"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return Invoice.objects.all().select_related("payment")
        if user.role == "instructor":
            return Invoice.objects.filter(payment__course__instructor=user).select_related(
                "payment"
            )
        return Invoice.objects.filter(payment__user=user).select_related("payment")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return InvoiceDetailSerializer
        return InvoiceListSerializer
