"""Payments app admin configuration"""

from django.contrib import admin
from .models import Price, Payment, Invoice, PaymentLog


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    """Admin for course pricing"""

    list_display = [
        "course",
        "amount",
        "currency",
        "discount_percent",
        "is_active",
        "created_at",
    ]
    list_filter = ["currency", "is_active", "created_at"]
    search_fields = ["course__title"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin for payments"""

    list_display = [
        "user",
        "course",
        "amount",
        "currency",
        "status",
        "transaction_id",
        "initiated_at",
    ]
    list_filter = ["status", "payment_method", "currency", "initiated_at"]
    search_fields = [
        "user__name",
        "user__email",
        "course__title",
        "transaction_id",
    ]
    readonly_fields = [
        "initiated_at",
        "completed_at",
        "created_at",
        "updated_at",
    ]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    """Admin for invoices"""

    list_display = [
        "invoice_number",
        "payment",
        "status",
        "total_amount",
        "issued_date",
        "due_date",
        "paid_date",
    ]
    list_filter = ["status", "issued_date"]
    search_fields = ["invoice_number", "payment__user__name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(PaymentLog)
class PaymentLogAdmin(admin.ModelAdmin):
    """Admin for payment logs"""

    list_display = [
        "payment",
        "log_type",
        "message",
        "created_at",
    ]
    list_filter = ["log_type", "created_at"]
    search_fields = ["payment__user__name", "message"]
    readonly_fields = ["created_at"]
