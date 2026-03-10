"""Tests for notifications"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.users.models import User
from .models import NotificationTemplate, Notification


class NotificationTemplateTests(TestCase):
    """Test notification templates"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="user@example.com",
            name="Test User",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )

    def test_list_templates_requires_auth(self):
        """Test listing templates requires authentication"""
        response = self.client.get(reverse("notification-template-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_templates(self):
        """Test listing notification templates"""
        NotificationTemplate.objects.create(
            trigger=NotificationTemplate.TRIGGER_COURSE_PUBLISHED,
            name="Course Published",
            subject="New Course Available",
            message="A new course is now available",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("notification-template-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_filter_templates_by_trigger(self):
        """Test filtering templates by trigger"""
        NotificationTemplate.objects.create(
            trigger=NotificationTemplate.TRIGGER_COURSE_PUBLISHED,
            name="Course Published",
            subject="New Course Available",
            message="A new course is now available",
            is_active=True,
        )
        NotificationTemplate.objects.create(
            trigger=NotificationTemplate.TRIGGER_ENROLLMENT_CONFIRMED,
            name="Enrollment Confirmed",
            subject="Enrollment Confirmed",
            message="You are enrolled",
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("notification-template-list"),
            {"trigger": NotificationTemplate.TRIGGER_COURSE_PUBLISHED},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)


class NotificationPreferenceTests(TestCase):
    """Test notification preferences"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="user@example.com",
            name="Test User",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )

    def test_get_default_preferences(self):
        """Test getting default notification preferences"""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("notification-preference-my-preferences"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["enable_in_app"])
        self.assertTrue(response.data["enable_email"])

    def test_update_preferences(self):
        """Test updating notification preferences"""
        self.client.force_authenticate(user=self.user)
        response = self.client.put(
            reverse("notification-preference-my-preferences"),
            {
                "enable_email": False,
                "email_digest_frequency": "weekly",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["enable_email"])
        self.assertEqual(response.data["email_digest_frequency"], "weekly")

    def test_preferences_requires_auth(self):
        """Test preferences endpoint requires auth"""
        response = self.client.get(reverse("notification-preference-my-preferences"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NotificationTests(TestCase):
    """Test notifications"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="user@example.com",
            name="Test User",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.template = NotificationTemplate.objects.create(
            trigger=NotificationTemplate.TRIGGER_COURSE_PUBLISHED,
            name="Course Published",
            subject="New Course",
            message="Course is published",
        )

    def test_list_notifications_requires_auth(self):
        """Test listing notifications requires auth"""
        response = self.client.get(reverse("notification-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_own_notifications(self):
        """Test user sees only their notifications"""
        Notification.objects.create(
            user=self.user,
            subject="Test",
            message="Test message",
            notification_type=Notification.NOTIFICATION_TYPE_INFO,
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        Notification.objects.create(
            user=other_user,
            subject="Other",
            message="Other message",
            notification_type=Notification.NOTIFICATION_TYPE_INFO,
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("notification-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_filter_notifications_by_read_status(self):
        """Test filtering notifications by read status"""
        Notification.objects.create(
            user=self.user,
            subject="Unread",
            message="Message",
            is_read=False,
        )
        Notification.objects.create(
            user=self.user,
            subject="Read",
            message="Message",
            is_read=True,
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("notification-list"),
            {"is_read": "false"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_mark_as_read(self):
        """Test marking notification as read"""
        notification = Notification.objects.create(
            user=self.user,
            subject="Test",
            message="Message",
            is_read=False,
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse("notification-mark-as-read", args=[notification.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_read"])

    def test_mark_all_as_read(self):
        """Test marking all notifications as read"""
        Notification.objects.create(
            user=self.user,
            subject="Test 1",
            message="Message 1",
            is_read=False,
        )
        Notification.objects.create(
            user=self.user,
            subject="Test 2",
            message="Message 2",
            is_read=False,
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse("notification-mark-all-as-read"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_unread_count(self):
        """Test getting unread notification count"""
        Notification.objects.create(
            user=self.user,
            subject="Test 1",
            message="Message",
            is_read=False,
        )
        Notification.objects.create(
            user=self.user,
            subject="Test 2",
            message="Message",
            is_read=True,
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("notification-unread-count"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["unread_count"], 1)

    def test_delete_notification(self):
        """Test deleting a notification"""
        notification = Notification.objects.create(
            user=self.user,
            subject="Test",
            message="Message",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(
            reverse("notification-delete-notification", args=[notification.id])
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_cannot_delete_others_notification(self):
        """Test user cannot delete others' notifications"""
        other_user = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        notification = Notification.objects.create(
            user=other_user,
            subject="Test",
            message="Message",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(
            reverse("notification-delete-notification", args=[notification.id])
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_all_read(self):
        """Test deleting all read notifications"""
        Notification.objects.create(
            user=self.user,
            subject="Read 1",
            message="Message",
            is_read=True,
        )
        Notification.objects.create(
            user=self.user,
            subject="Read 2",
            message="Message",
            is_read=True,
        )
        Notification.objects.create(
            user=self.user,
            subject="Unread",
            message="Message",
            is_read=False,
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(reverse("notification-delete-all-read"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_retrieve_notification(self):
        """Test retrieving notification detail"""
        notification = Notification.objects.create(
            user=self.user,
            subject="Test",
            message="Message",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("notification-detail", args=[notification.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["subject"], "Test")

    def test_cannot_view_others_notification(self):
        """Test user cannot view others' notifications"""
        other_user = User.objects.create_user(
            email="other@example.com",
            name="Other",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        notification = Notification.objects.create(
            user=other_user,
            subject="Test",
            message="Message",
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("notification-detail", args=[notification.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
