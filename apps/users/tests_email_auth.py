"""Tests for email auth flows: registration verification, password reset."""

from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User


class EmailVerificationFlowTests(TestCase):
    """POST /api/v1/auth/email-verify/ validates token and marks user verified."""

    def setUp(self):
        self.client: APIClient = APIClient()
        self.user = User.objects.create_user(
            email="verify@test.com",
            name="Verify User",
            password="TestPass123!",
            role=User.ROLE_STUDENT,
        )

    @patch("apps.users.views.email_service")
    def test_register_sends_verification_email(self, mock_email_service):
        """POST /register triggers a verification email send."""
        response = self.client.post(
            reverse("register"),
            {
                "email": "new@test.com",
                "name": "New User",
                "password": "TestPass123!",
                "role": "student",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        mock_email_service.send_verification_email.assert_called_once()

    def test_verify_email_with_valid_token(self):
        """Valid token marks user email_verified=True."""
        from apps.users.token_service import generate_token

        token = generate_token("email_verify", self.user.id)

        response = self.client.post(reverse("verify_email"), {"token": token})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.email_verified)

    def test_verify_email_with_invalid_token(self):
        """Invalid/expired token returns 400."""
        response = self.client.post(reverse("verify_email"), {"token": "bad-token"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_email_token_consumed(self):
        """Token cannot be reused after successful verification."""
        from apps.users.token_service import generate_token

        token = generate_token("email_verify", self.user.id)

        self.client.post(reverse("verify_email"), {"token": token})
        # Second attempt with same token
        response = self.client.post(reverse("verify_email"), {"token": token})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PasswordResetFlowTests(TestCase):
    """Full password reset flow: request → email → confirm."""

    def setUp(self):
        self.client: APIClient = APIClient()
        self.user = User.objects.create_user(
            email="reset@test.com",
            name="Reset User",
            password="OldPass123!",
            role=User.ROLE_STUDENT,
        )

    @patch("apps.users.views.email_service")
    def test_reset_request_sends_email(self, mock_email_service):
        """POST /password-reset/ calls email_service.send_password_reset_email."""
        response = self.client.post(reverse("password_reset_request"), {"email": self.user.email})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_email_service.send_password_reset_email.assert_called_once()

    @patch("apps.users.views.email_service")
    def test_reset_request_unknown_email_still_200(self, mock_email_service):
        """Unknown email returns 200 to prevent user enumeration."""
        response = self.client.post(
            reverse("password_reset_request"), {"email": "unknown@test.com"}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_email_service.send_password_reset_email.assert_not_called()

    def test_reset_confirm_with_valid_token(self):
        """Valid token resets the password."""
        from apps.users.token_service import generate_token

        token = generate_token("password_reset", self.user.id)

        response = self.client.post(
            reverse("password_reset_confirm"),
            {"token": token, "new_password": "NewPass456!", "new_password2": "NewPass456!"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass456!"))

    def test_reset_confirm_with_invalid_token(self):
        """Invalid token returns 400."""
        response = self.client.post(
            reverse("password_reset_confirm"),
            {"token": "garbage", "new_password": "NewPass456!", "new_password2": "NewPass456!"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_confirm_token_consumed(self):
        """Token cannot be reused after successful reset."""
        from apps.users.token_service import generate_token

        token = generate_token("password_reset", self.user.id)

        self.client.post(
            reverse("password_reset_confirm"),
            {"token": token, "new_password": "NewPass456!", "new_password2": "NewPass456!"},
        )
        # Second attempt
        response = self.client.post(
            reverse("password_reset_confirm"),
            {"token": token, "new_password": "AnotherPass789!", "new_password2": "AnotherPass789!"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_confirm_mismatched_passwords(self):
        """Mismatched new_password / new_password2 returns 400."""
        from apps.users.token_service import generate_token

        token = generate_token("password_reset", self.user.id)

        response = self.client.post(
            reverse("password_reset_confirm"),
            {"token": token, "new_password": "NewPass456!", "new_password2": "Different789!"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
