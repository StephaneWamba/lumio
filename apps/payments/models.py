"""Payments app models"""

from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from apps.courses.models import Course
from apps.users.models import User


class Price(models.Model):
    """Course pricing"""

    CURRENCY_USD = "USD"
    CURRENCY_EUR = "EUR"
    CURRENCY_GBP = "GBP"

    CURRENCY_CHOICES = [
        (CURRENCY_USD, "US Dollar"),
        (CURRENCY_EUR, "Euro"),
        (CURRENCY_GBP, "British Pound"),
    ]

    course = models.OneToOneField(
        Course,
        on_delete=models.CASCADE,
        related_name="pricing",
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Price in currency units",
    )
    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=CURRENCY_USD,
    )

    # Discount
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )
    discount_until = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Discount valid until this date",
    )

    # Status
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Price"
        verbose_name_plural = "Prices"

    def __str__(self):
        return f"{self.course.title} - {self.amount} {self.currency}"

    @property
    def discounted_amount(self):
        """Calculate discounted amount if applicable"""
        if self.discount_percent > 0:
            if self.discount_until and timezone.now() < self.discount_until:
                discount = self.amount * (self.discount_percent / 100)
                return self.amount - discount
        return self.amount

    @property
    def is_discount_active(self):
        """Check if discount is currently active"""
        if self.discount_percent > 0:
            if self.discount_until and timezone.now() < self.discount_until:
                return True
        return False


class Payment(models.Model):
    """Payment transactions"""

    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_REFUNDED = "refunded"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_PROCESSING, "Processing"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_FAILED, "Failed"),
        (STATUS_REFUNDED, "Refunded"),
    ]

    PAYMENT_METHOD_CREDIT_CARD = "credit_card"
    PAYMENT_METHOD_PAYPAL = "paypal"
    PAYMENT_METHOD_BANK_TRANSFER = "bank_transfer"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_CREDIT_CARD, "Credit Card"),
        (PAYMENT_METHOD_PAYPAL, "PayPal"),
        (PAYMENT_METHOD_BANK_TRANSFER, "Bank Transfer"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="payments",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.SET_NULL,
        null=True,
        related_name="payments",
    )

    # Payment details
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    currency = models.CharField(
        max_length=3,
        default="USD",
    )
    payment_method = models.CharField(
        max_length=50,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_METHOD_CREDIT_CARD,
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    # External reference
    transaction_id = models.CharField(
        max_length=255,
        unique=True,
        help_text="External payment processor transaction ID",
    )
    processor_response = models.TextField(blank=True)

    # Refund
    is_refunded = models.BooleanField(default=False)
    refunded_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    refunded_at = models.DateTimeField(blank=True, null=True)
    refund_reason = models.TextField(blank=True)

    # Timestamps
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-initiated_at"]
        indexes = [
            models.Index(fields=["user", "-initiated_at"]),
            models.Index(fields=["status", "-initiated_at"]),
        ]

    def __str__(self):
        user_name = self.user.name if self.user else "Unknown"
        return f"{user_name} - {self.amount} {self.currency}"


class Invoice(models.Model):
    """Billing invoices"""

    STATUS_DRAFT = "draft"
    STATUS_ISSUED = "issued"
    STATUS_PAID = "paid"
    STATUS_OVERDUE = "overdue"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_ISSUED, "Issued"),
        (STATUS_PAID, "Paid"),
        (STATUS_OVERDUE, "Overdue"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    payment = models.OneToOneField(
        Payment,
        on_delete=models.CASCADE,
        related_name="invoice",
    )

    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Invoice number for reference",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
    )

    # Invoice details
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    # Billing dates
    issued_date = models.DateField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    paid_date = models.DateField(blank=True, null=True)

    # Notes
    notes = models.TextField(blank=True)
    terms = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        ordering = ["-issued_date"]

    def __str__(self):
        return f"Invoice {self.invoice_number}"


class PaymentLog(models.Model):
    """Audit log for payments"""

    LOG_TYPE_CREATED = "created"
    LOG_TYPE_INITIATED = "initiated"
    LOG_TYPE_PROCESSING = "processing"
    LOG_TYPE_COMPLETED = "completed"
    LOG_TYPE_FAILED = "failed"
    LOG_TYPE_REFUND_INITIATED = "refund_initiated"
    LOG_TYPE_REFUNDED = "refunded"

    LOG_TYPE_CHOICES = [
        (LOG_TYPE_CREATED, "Created"),
        (LOG_TYPE_INITIATED, "Initiated"),
        (LOG_TYPE_PROCESSING, "Processing"),
        (LOG_TYPE_COMPLETED, "Completed"),
        (LOG_TYPE_FAILED, "Failed"),
        (LOG_TYPE_REFUND_INITIATED, "Refund Initiated"),
        (LOG_TYPE_REFUNDED, "Refunded"),
    ]

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    log_type = models.CharField(
        max_length=20,
        choices=LOG_TYPE_CHOICES,
    )
    message = models.TextField()
    details = models.TextField(blank=True, help_text="JSON details of the log entry")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Payment Log"
        verbose_name_plural = "Payment Logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["payment", "-created_at"]),
            models.Index(fields=["log_type", "-created_at"]),
        ]

    def __str__(self):
        user_name = self.payment.user.name if self.payment.user else "Unknown"
        return f"{user_name} - {self.get_log_type_display()}"
