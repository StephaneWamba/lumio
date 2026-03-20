"""Tests for user authentication and permissions"""

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import User, InstructorProfile


class UserAuthenticationTests(TestCase):
    """Test user authentication flows"""

    def setUp(self):
        """Set up test client and create test user"""
        self.client = APIClient()
        self.register_url = reverse("register")
        self.login_url = reverse("login")
        self.token_url = reverse("token_obtain_pair")

        self.user_data = {
            "email": "wambstephane@gmail.com",
            "name": "Test User",
            "password": "TestPassword123!",
            "password2": "TestPassword123!",
            "role": User.ROLE_STUDENT,
        }

    def test_user_registration(self):
        """Test user can register"""
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.filter(email=self.user_data["email"]).count(), 1)
        self.assertEqual(User.objects.first().email, self.user_data["email"])

    def test_user_registration_password_mismatch(self):
        """Test registration fails with mismatched passwords"""
        data = self.user_data.copy()
        data["password2"] = "DifferentPassword123!"
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(User.objects.filter(email=data["email"]).count(), 0)

    def test_user_registration_weak_password(self):
        """Test registration fails with weak password"""
        data = self.user_data.copy()
        data["password"] = "weak"
        data["password2"] = "weak"
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_registration_duplicate_email(self):
        """Test registration fails with duplicate email"""
        User.objects.create_user(
            email="wambstephane@gmail.com",
            name="Existing User",
            password="TestPassword123!",
        )
        response = self.client.post(self.register_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_login(self):
        """Test user can login"""
        # Create user
        User.objects.create_user(
            email=self.user_data["email"],
            name=self.user_data["name"],
            password=self.user_data["password"],
        )

        # Login
        login_data = {
            "email": self.user_data["email"],
            "password": self.user_data["password"],
        }
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_user_login_invalid_credentials(self):
        """Test login fails with invalid credentials"""
        User.objects.create_user(
            email=self.user_data["email"],
            name=self.user_data["name"],
            password=self.user_data["password"],
        )

        login_data = {
            "email": self.user_data["email"],
            "password": "WrongPassword123!",
        }
        response = self.client.post(self.login_url, login_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_jwt_token_obtain(self):
        """Test JWT token endpoint"""
        user = User.objects.create_user(
            email=self.user_data["email"],
            name=self.user_data["name"],
            password=self.user_data["password"],
        )

        response = self.client.post(
            self.token_url,
            {
                "email": self.user_data["email"],
                "password": self.user_data["password"],
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_jwt_token_refresh(self):
        """Test JWT token refresh"""
        user = User.objects.create_user(
            email=self.user_data["email"],
            name=self.user_data["name"],
            password=self.user_data["password"],
        )

        # Get tokens
        response = self.client.post(
            self.token_url,
            {
                "email": self.user_data["email"],
                "password": self.user_data["password"],
            },
        )
        refresh_token = response.data["refresh"]

        # Refresh
        response = self.client.post(
            reverse("token_refresh"),
            {"refresh": refresh_token},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)

    def test_jwt_token_invalid_refresh(self):
        """Test JWT refresh fails with invalid token"""
        response = self.client.post(
            reverse("token_refresh"),
            {"refresh": "invalid_token"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserProfileTests(TestCase):
    """Test user profile access and modification"""

    def setUp(self):
        """Set up test client and create test user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="testuser@example.com",
            name="Test User",
            password="TestPassword123!",
        )
        self.client.force_authenticate(user=self.user)

    def test_get_current_user_profile(self):
        """Test getting current user profile"""
        response = self.client.get(reverse("user-me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)

    def test_update_user_profile(self):
        """Test updating user profile"""
        new_name = "Updated Name"
        response = self.client.put(
            reverse("user-update-profile"),
            {"name": new_name},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, new_name)

    def test_change_password(self):
        """Test changing password"""
        new_password = "NewPassword123!"
        response = self.client.post(
            reverse("user-change-password"),
            {
                "old_password": "TestPassword123!",
                "new_password": new_password,
                "new_password2": new_password,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(new_password))

    def test_change_password_wrong_old(self):
        """Test changing password with wrong old password"""
        response = self.client.post(
            reverse("user-change-password"),
            {
                "old_password": "WrongPassword123!",
                "new_password": "NewPassword123!",
                "new_password2": "NewPassword123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class InstructorProfileTests(TestCase):
    """Test instructor profile management"""

    def setUp(self):
        """Set up test client and create instructor user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="instructor@example.com",
            name="Instructor User",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.profile = InstructorProfile.objects.create(
            user=self.user,
            bio="Test instructor",
        )
        self.client.force_authenticate(user=self.user)

    def test_get_instructor_profile(self):
        """Test getting instructor profile"""
        response = self.client.get(reverse("instructor-profile-my-profile"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["email"], self.user.email)

    def test_update_instructor_profile(self):
        """Test updating instructor profile"""
        new_bio = "Updated bio"
        response = self.client.patch(
            reverse("instructor-profile-detail", args=[self.profile.id]),
            {"bio": new_bio},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.bio, new_bio)


class PermissionTests(TestCase):
    """Test custom permissions"""

    def setUp(self):
        """Set up test users"""
        self.student = User.objects.create_user(
            email="student@example.com",
            name="Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.instructor = User.objects.create_user(
            email="instructor@example.com",
            name="Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            name="Admin",
            password="TestPassword123!",
            role=User.ROLE_ADMIN,
        )

    def test_student_permission(self):
        """Test student permission check"""
        from apps.users.permissions import IsStudent

        permission = IsStudent()
        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

        # Create mock request
        request = self.client.get("/").wsgi_request
        request.user = self.student

        self.assertTrue(permission.has_permission(request, None))

    def test_instructor_permission(self):
        """Test instructor permission check"""
        from apps.users.permissions import IsInstructor

        permission = IsInstructor()
        self.client = APIClient()

        # Create instructor profile with is_approved=True
        InstructorProfile.objects.create(
            user=self.instructor,
            is_approved=True,
        )

        self.client.force_authenticate(user=self.instructor)
        request = self.client.get("/").wsgi_request
        request.user = self.instructor

        self.assertTrue(permission.has_permission(request, None))


class PasswordResetTests(TestCase):
    """Test password reset flow"""

    def setUp(self):
        """Set up test client and create test user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="wambstephane@gmail.com",
            name="Test User",
            password="TestPassword123!",
        )
        self.password_reset_url = reverse("password_reset_request")
        self.password_reset_confirm_url = reverse("password_reset_confirm")

    def test_password_reset_request(self):
        """Test password reset request endpoint"""
        response = self.client.post(
            self.password_reset_url,
            {"email": "wambstephane@gmail.com"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)

    def test_password_reset_request_nonexistent_email(self):
        """Test password reset request with non-existent email returns 200 (anti-enumeration)"""
        response = self.client.post(
            self.password_reset_url,
            {"email": "nonexistent@example.com"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm(self):
        """Test password reset confirm endpoint"""
        from apps.users.token_service import generate_token

        token = generate_token("password_reset", self.user.id)
        response = self.client.post(
            self.password_reset_confirm_url,
            {
                "token": token,
                "new_password": "NewPassword123!",
                "new_password2": "NewPassword123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_password_reset_confirm_password_mismatch(self):
        """Test password reset confirm with mismatched passwords"""
        response = self.client.post(
            self.password_reset_confirm_url,
            {
                "token": "dummy_token",
                "new_password": "NewPassword123!",
                "new_password2": "DifferentPassword123!",
            },
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class EmailVerificationTests(TestCase):
    """Test email verification flow"""

    def setUp(self):
        """Set up test client"""
        self.client = APIClient()
        self.verify_email_url = reverse("verify_email")

    def test_email_verification(self):
        """Test email verification endpoint"""
        from apps.users.token_service import generate_token

        user = User.objects.create_user(
            email="wambstephane@gmail.com",
            name="Verify User",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        token = generate_token("email_verify", user.id)
        response = self.client.post(
            self.verify_email_url,
            {"token": token},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("message", response.data)
