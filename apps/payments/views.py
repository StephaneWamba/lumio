"""Payments app views"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.shortcuts import get_object_or_404
from decimal import Decimal
import uuid

from .models import Price, Payment, Invoice, PaymentLog
from .serializers import (
    PriceSerializer,
    PaymentListSerializer,
    PaymentDetailSerializer,
    InvoiceListSerializer,
    InvoiceDetailSerializer,
)
from apps.courses.models import Course


class PriceViewSet(viewsets.ModelViewSet):
    """ViewSet for course pricing"""

    queryset = Price.objects.all()
    serializer_class = PriceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter prices by user role"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return Price.objects.all()
        if user.role == "instructor":
            return Price.objects.filter(course__instructor=user)
        # Students see active prices for available courses
        return Price.objects.filter(is_active=True)

    def perform_create(self, serializer):
        """Create price for a course"""
        course = get_object_or_404(
            Course,
            id=self.request.data.get("course_id"),
        )
        if self.request.user != course.instructor and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save()

    def perform_update(self, serializer):
        """Update price"""
        course = serializer.instance.course
        if self.request.user != course.instructor and not self.request.user.is_staff:
            self.permission_denied(self.request)
        serializer.save()


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for payments"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter payments by user role"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return Payment.objects.all().select_related("user", "course")
        if user.role == "instructor":
            return Payment.objects.filter(course__instructor=user).select_related("user", "course")
        # Students see only their own payments
        return Payment.objects.filter(user=user).select_related("user", "course")

    def get_serializer_class(self):
        """Use detail serializer for retrieve"""
        if self.action == "retrieve":
            return PaymentDetailSerializer
        return PaymentListSerializer

    @action(detail=False, methods=["post"])
    def initiate_payment(self, request):
        """Initiate a payment for a course"""
        course_id = request.data.get("course_id")
        payment_method = request.data.get("payment_method", "credit_card")

        if not course_id:
            return Response(
                {"detail": "course_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course = get_object_or_404(Course, id=course_id)

        # Check if course has pricing
        if not hasattr(course, "price"):
            return Response(
                {"detail": "Course does not have pricing configured"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create payment
        price = course.price
        amount = price.discounted_amount if price.is_discount_active else price.amount

        transaction_id = f"TXN-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

        payment = Payment.objects.create(
            user=request.user,
            course=course,
            amount=amount,
            currency=price.currency,
            payment_method=payment_method,
            transaction_id=transaction_id,
            status=Payment.STATUS_PENDING,
        )

        # Log the creation
        PaymentLog.objects.create(
            payment=payment,
            log_type=PaymentLog.LOG_TYPE_CREATED,
            message=f"Payment initiated for {course.title}",
        )

        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def complete_payment(self, request, pk=None):
        """Complete a payment"""
        payment = self.get_object()

        if payment.user != request.user and not request.user.is_staff:
            self.permission_denied(request)

        if payment.status != Payment.STATUS_PENDING:
            return Response(
                {"detail": "Payment is not in pending status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark as completed
        payment.status = Payment.STATUS_COMPLETED
        payment.completed_at = timezone.now()
        payment.save()

        # Log the completion
        PaymentLog.objects.create(
            payment=payment,
            log_type=PaymentLog.LOG_TYPE_COMPLETED,
            message="Payment completed",
            details=request.data.get("details", ""),
        )

        # Create invoice
        invoice_number = f"INV-{timezone.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        Invoice.objects.create(
            payment=payment,
            invoice_number=invoice_number,
            status=Invoice.STATUS_ISSUED,
            subtotal=payment.amount,
            tax_amount=Decimal("0.00"),
            total_amount=payment.amount,
            issued_date=timezone.now().date(),
        )

        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def mark_failed(self, request, pk=None):
        """Mark payment as failed"""
        payment = self.get_object()

        if payment.user != request.user and not request.user.is_staff:
            self.permission_denied(request)

        payment.status = Payment.STATUS_FAILED
        payment.processor_response = request.data.get("error_message", "")
        payment.save()

        # Log the failure
        PaymentLog.objects.create(
            payment=payment,
            log_type=PaymentLog.LOG_TYPE_FAILED,
            message="Payment failed",
            details=payment.processor_response,
        )

        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        """Refund a payment"""
        payment = self.get_object()

        if payment.course.instructor != request.user and not request.user.is_staff:
            self.permission_denied(request)

        if payment.status != Payment.STATUS_COMPLETED:
            return Response(
                {"detail": "Payment is not in completed status"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if payment.is_refunded:
            return Response(
                {"detail": "Payment is already refunded"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Refund the payment
        refund_amount = request.data.get("amount", payment.amount)
        payment.is_refunded = True
        payment.refunded_amount = refund_amount
        payment.refunded_at = timezone.now()
        payment.refund_reason = request.data.get("reason", "")
        payment.status = Payment.STATUS_REFUNDED
        payment.save()

        # Log the refund
        PaymentLog.objects.create(
            payment=payment,
            log_type=PaymentLog.LOG_TYPE_REFUNDED,
            message=f"Payment refunded: {refund_amount} {payment.currency}",
            details=payment.refund_reason,
        )

        serializer = PaymentDetailSerializer(payment)
        return Response(serializer.data, status=status.HTTP_200_OK)


class InvoiceViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for invoices"""

    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Filter invoices by user role"""
        user = self.request.user
        if user.is_staff or user.role == "admin":
            return Invoice.objects.all().select_related("payment")
        if user.role == "instructor":
            return Invoice.objects.filter(payment__course__instructor=user).select_related(
                "payment"
            )
        # Students see only their own invoices
        return Invoice.objects.filter(payment__user=user).select_related("payment")

    def get_serializer_class(self):
        """Use detail serializer for retrieve"""
        if self.action == "retrieve":
            return InvoiceDetailSerializer
        return InvoiceListSerializer
