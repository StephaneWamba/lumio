"""User models: custom User, profiles, authentication"""
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.utils.timezone import now


class UserManager(BaseUserManager):
    """Custom user manager"""

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular user"""
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a superuser"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user model with email-based auth and roles"""

    ROLE_STUDENT = "student"
    ROLE_INSTRUCTOR = "instructor"
    ROLE_ADMIN = "admin"
    ROLE_CORPORATE_MANAGER = "corporate_manager"

    ROLE_CHOICES = [
        (ROLE_STUDENT, "Student"),
        (ROLE_INSTRUCTOR, "Instructor"),
        (ROLE_ADMIN, "Admin"),
        (ROLE_CORPORATE_MANAGER, "Corporate Manager"),
    ]

    id = models.BigAutoField(primary_key=True)
    email = models.EmailField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    avatar_url = models.URLField(blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STUDENT)

    # Account status
    is_active = models.BooleanField(default=True, db_index=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Dates
    date_joined = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Email verification
    email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["role", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.email})"

    def mark_email_as_verified(self) -> None:
        """Mark email as verified"""
        self.email_verified = True
        self.email_verified_at = now()
        self.save(update_fields=["email_verified", "email_verified_at"])


class InstructorProfile(models.Model):
    """Instructor-specific profile data"""

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="instructor_profile")

    bio = models.TextField(blank=True)
    website = models.URLField(blank=True)

    # Payments
    stripe_account_id = models.CharField(max_length=255, blank=True, null=True)
    stripe_onboarded = models.BooleanField(default=False)

    # Approval status
    is_approved = models.BooleanField(default=False, db_index=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_instructors")

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Instructor: {self.user.name}"

    def approve(self, approved_by: User) -> None:
        """Mark instructor as approved"""
        self.is_approved = True
        self.approved_at = now()
        self.approved_by = approved_by
        self.save(update_fields=["is_approved", "approved_at", "approved_by"])


class CorporateManagerProfile(models.Model):
    """Corporate manager profile for B2B enrollments"""

    id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="corporate_profile")

    company_name = models.CharField(max_length=255)
    team_size = models.IntegerField(default=0)

    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Corporate Manager: {self.user.name} ({self.company_name})"
