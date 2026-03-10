"""Payments app serializers"""

from rest_framework import serializers
from .models import Price, Payment, Invoice, PaymentLog
from apps.courses.serializers import CourseListSerializer
from apps.users.serializers import UserSerializer


class PriceSerializer(serializers.ModelSerializer):
    """Serializer for course pricing"""

    course = CourseListSerializer(read_only=True)
    course_id = serializers.IntegerField(write_only=True)
    discounted_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    is_discount_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Price
        fields = [
            "id",
            "course",
            "course_id",
            "amount",
            "currency",
            "discount_percent",
            "discount_until",
            "discounted_amount",
            "is_discount_active",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class PaymentLogSerializer(serializers.ModelSerializer):
    """Serializer for payment logs"""

    log_type_display = serializers.CharField(
        source="get_log_type_display",
        read_only=True,
    )

    class Meta:
        model = PaymentLog
        fields = [
            "id",
            "log_type",
            "log_type_display",
            "message",
            "details",
            "created_at",
        ]
        read_only_fields = fields


class PaymentListSerializer(serializers.ModelSerializer):
    """Serializer for listing payments"""

    user_name = serializers.CharField(
        source="user.name",
        read_only=True,
    )
    course_title = serializers.CharField(
        source="course.title",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "user_name",
            "course_title",
            "amount",
            "currency",
            "status",
            "status_display",
            "transaction_id",
            "initiated_at",
            "completed_at",
        ]
        read_only_fields = fields


class PaymentDetailSerializer(serializers.ModelSerializer):
    """Serializer for payment detail"""

    user = UserSerializer(read_only=True)
    course = CourseListSerializer(read_only=True)
    logs = PaymentLogSerializer(many=True, read_only=True)
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )
    payment_method_display = serializers.CharField(
        source="get_payment_method_display",
        read_only=True,
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "user",
            "course",
            "amount",
            "currency",
            "payment_method",
            "payment_method_display",
            "status",
            "status_display",
            "transaction_id",
            "processor_response",
            "is_refunded",
            "refunded_amount",
            "refunded_at",
            "refund_reason",
            "initiated_at",
            "completed_at",
            "logs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "user",
            "course",
            "status",
            "transaction_id",
            "processor_response",
            "is_refunded",
            "refunded_amount",
            "refunded_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]


class InvoiceListSerializer(serializers.ModelSerializer):
    """Serializer for listing invoices"""

    user_name = serializers.CharField(
        source="payment.user.name",
        read_only=True,
    )
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Invoice
        fields = [
            "id",
            "invoice_number",
            "user_name",
            "status",
            "status_display",
            "total_amount",
            "issued_date",
            "due_date",
            "paid_date",
        ]
        read_only_fields = fields


class InvoiceDetailSerializer(serializers.ModelSerializer):
    """Serializer for invoice detail"""

    payment = PaymentDetailSerializer(read_only=True)
    status_display = serializers.CharField(
        source="get_status_display",
        read_only=True,
    )

    class Meta:
        model = Invoice
        fields = [
            "id",
            "payment",
            "invoice_number",
            "status",
            "status_display",
            "subtotal",
            "tax_amount",
            "total_amount",
            "issued_date",
            "due_date",
            "paid_date",
            "notes",
            "terms",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "payment",
            "invoice_number",
            "created_at",
            "updated_at",
        ]
