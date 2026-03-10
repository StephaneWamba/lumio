"""Notifications app serializers"""

from rest_framework import serializers
from .models import NotificationTemplate, NotificationPreference, Notification, NotificationLog
from apps.users.serializers import UserSerializer


class NotificationTemplateSerializer(serializers.ModelSerializer):
    """Serializer for notification templates"""

    class Meta:
        model = NotificationTemplate
        fields = [
            "id",
            "trigger",
            "name",
            "subject",
            "message",
            "send_in_app",
            "send_email",
            "send_push",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    """Serializer for notification preferences"""

    user = UserSerializer(read_only=True)

    class Meta:
        model = NotificationPreference
        fields = [
            "id",
            "user",
            "enable_in_app",
            "enable_email",
            "enable_push",
            "email_digest_frequency",
            "enabled_categories",
            "updated_at",
        ]
        read_only_fields = ["user", "updated_at"]


class NotificationLogSerializer(serializers.ModelSerializer):
    """Serializer for notification logs"""

    log_type_display = serializers.CharField(
        source="get_log_type_display",
        read_only=True,
    )

    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "log_type",
            "log_type_display",
            "details",
            "created_at",
        ]
        read_only_fields = fields


class NotificationListSerializer(serializers.ModelSerializer):
    """Serializer for listing notifications"""

    type_display = serializers.CharField(
        source="get_notification_type_display",
        read_only=True,
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "notification_type",
            "type_display",
            "subject",
            "message",
            "is_read",
            "action_url",
            "created_at",
        ]
        read_only_fields = fields


class NotificationDetailSerializer(serializers.ModelSerializer):
    """Serializer for notification detail"""

    user = UserSerializer(read_only=True)
    template = NotificationTemplateSerializer(read_only=True)
    logs = NotificationLogSerializer(many=True, read_only=True)
    type_display = serializers.CharField(
        source="get_notification_type_display",
        read_only=True,
    )

    class Meta:
        model = Notification
        fields = [
            "id",
            "user",
            "template",
            "notification_type",
            "type_display",
            "subject",
            "message",
            "action_url",
            "is_read",
            "read_at",
            "email_sent",
            "email_sent_at",
            "push_sent",
            "push_sent_at",
            "logs",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "user",
            "template",
            "email_sent",
            "email_sent_at",
            "push_sent",
            "push_sent_at",
            "created_at",
            "updated_at",
        ]
