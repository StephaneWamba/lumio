"""Notifications app admin configuration"""

from django.contrib import admin
from .models import (
    NotificationTemplate,
    NotificationPreference,
    Notification,
    NotificationLog,
)


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    """Admin for notification templates"""

    list_display = [
        "trigger",
        "name",
        "send_in_app",
        "send_email",
        "send_push",
        "is_active",
    ]
    list_filter = ["trigger", "is_active", "send_in_app", "send_email"]
    search_fields = ["name", "subject", "message"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """Admin for notification preferences"""

    list_display = [
        "user",
        "enable_in_app",
        "enable_email",
        "enable_push",
        "email_digest_frequency",
    ]
    list_filter = [
        "enable_in_app",
        "enable_email",
        "enable_push",
        "email_digest_frequency",
    ]
    search_fields = ["user__name", "user__email"]
    readonly_fields = ["updated_at"]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin for notifications"""

    list_display = [
        "user",
        "notification_type",
        "subject",
        "is_read",
        "email_sent",
        "push_sent",
        "created_at",
    ]
    list_filter = [
        "notification_type",
        "is_read",
        "email_sent",
        "push_sent",
        "created_at",
    ]
    search_fields = ["user__name", "user__email", "subject"]
    readonly_fields = ["created_at", "updated_at", "read_at"]


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    """Admin for notification logs"""

    list_display = [
        "notification",
        "log_type",
        "created_at",
    ]
    list_filter = ["log_type", "created_at"]
    search_fields = [
        "notification__user__name",
        "notification__subject",
    ]
    readonly_fields = ["created_at"]
