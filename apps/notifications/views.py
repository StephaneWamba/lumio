"""Notifications app views"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, SAFE_METHODS
from rest_framework.response import Response
from apps.users.permissions import IsAdmin, IsInstructor
from .models import (
    NotificationTemplate,
    NotificationPreference,
    Notification,
    NotificationLog,
)
from .serializers import (
    NotificationTemplateSerializer,
    NotificationPreferenceSerializer,
    NotificationListSerializer,
    NotificationDetailSerializer,
    NotificationLogSerializer,
)


class NotificationTemplateViewSet(viewsets.ModelViewSet):
    """ViewSet for notification templates — instructors/admins can write"""

    queryset = NotificationTemplate.objects.all()
    serializer_class = NotificationTemplateSerializer
    filterset_fields = ["is_active", "trigger"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return [IsAuthenticated(), IsInstructor()]


class NotificationPreferenceViewSet(viewsets.ViewSet):
    """ViewSet for notification preferences"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get", "put"])
    def my_preferences(self, request):
        """Get or update user's notification preferences"""
        try:
            preferences = request.user.notification_preferences
        except NotificationPreference.DoesNotExist:
            # Create default preferences if they don't exist
            preferences = NotificationPreference.objects.create(user=request.user)

        if request.method == "GET":
            serializer = NotificationPreferenceSerializer(preferences)
            return Response(serializer.data)

        if request.method == "PUT":
            serializer = NotificationPreferenceSerializer(
                preferences,
                data=request.data,
                partial=True,
            )
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class NotificationViewSet(viewsets.ViewSet):
    """ViewSet for notifications"""

    permission_classes = [IsAuthenticated]

    def list(self, request):
        """List user's notifications"""
        notifications = Notification.objects.filter(user=request.user).order_by("-created_at")

        # Filter parameters
        is_read = request.query_params.get("is_read")
        notification_type = request.query_params.get("type")

        if is_read is not None:
            is_read = is_read.lower() == "true"
            notifications = notifications.filter(is_read=is_read)

        if notification_type:
            notifications = notifications.filter(notification_type=notification_type)

        # Pagination
        limit = int(request.query_params.get("limit", 20))
        offset = int(request.query_params.get("offset", 0))
        total = notifications.count()

        notifications = notifications[offset : offset + limit]
        serializer = NotificationListSerializer(notifications, many=True)

        return Response(
            {
                "count": total,
                "limit": limit,
                "offset": offset,
                "results": serializer.data,
            }
        )

    def retrieve(self, request, pk=None):
        """Get notification detail"""
        try:
            notification = Notification.objects.get(id=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response(
                {"detail": "Not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = NotificationDetailSerializer(notification)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def mark_as_read(self, request, pk=None):
        """Mark notification as read"""
        try:
            notification = Notification.objects.get(id=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response(
                {"detail": "Not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        notification.mark_as_read()

        # Log the action
        NotificationLog.objects.create(
            notification=notification,
            log_type=NotificationLog.LOG_TYPE_READ,
        )

        serializer = NotificationDetailSerializer(notification)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def mark_all_as_read(self, request):
        """Mark all unread notifications as read"""
        unread_notifications = Notification.objects.filter(
            user=request.user,
            is_read=False,
        )

        count = 0
        for notification in unread_notifications:
            notification.mark_as_read()
            NotificationLog.objects.create(
                notification=notification,
                log_type=NotificationLog.LOG_TYPE_READ,
            )
            count += 1

        return Response(
            {
                "detail": f"Marked {count} notifications as read",
                "count": count,
            }
        )

    @action(detail=False, methods=["get"])
    def unread_count(self, request):
        """Get count of unread notifications"""
        count = Notification.objects.filter(
            user=request.user,
            is_read=False,
        ).count()

        return Response({"unread_count": count})

    @action(detail=True, methods=["delete"])
    def delete_notification(self, request, pk=None):
        """Delete a notification"""
        try:
            notification = Notification.objects.get(id=pk, user=request.user)
        except Notification.DoesNotExist:
            return Response(
                {"detail": "Not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["delete"])
    def delete_all_read(self, request):
        """Delete all read notifications"""
        deleted_count, _ = Notification.objects.filter(
            user=request.user,
            is_read=True,
        ).delete()

        return Response(
            {
                "detail": f"Deleted {deleted_count} read notifications",
                "count": deleted_count,
            }
        )


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for notification logs (admin only)"""

    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    filterset_fields = ["notification", "log_type"]
    ordering_fields = ["-created_at"]
