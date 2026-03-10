"""User serializers for authentication and profile management"""
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, InstructorProfile, CorporateManagerProfile


class UserSerializer(serializers.ModelSerializer):
    """Base user serializer"""

    class Meta:
        model = User
        fields = ["id", "email", "name", "avatar_url", "role", "date_joined"]
        read_only_fields = ["id", "date_joined"]


class UserDetailSerializer(serializers.ModelSerializer):
    """Detailed user serializer with all fields"""

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "name",
            "avatar_url",
            "role",
            "email_verified",
            "is_active",
            "date_joined",
            "updated_at",
        ]
        read_only_fields = ["id", "date_joined", "updated_at", "email_verified"]


class RegisterSerializer(serializers.ModelSerializer):
    """User registration serializer"""

    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = ["email", "name", "password", "password2", "role"]

    def validate(self, attrs):
        """Validate password match"""
        if attrs["password"] != attrs.pop("password2"):
            raise serializers.ValidationError({"password": "Passwords must match."})
        return attrs

    def create(self, validated_data):
        """Create user and send verification email"""
        user = User.objects.create_user(
            email=validated_data["email"],
            name=validated_data["name"],
            password=validated_data["password"],
            role=validated_data.get("role", User.ROLE_STUDENT),
        )
        return user


class LoginSerializer(serializers.Serializer):
    """User login serializer"""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        """Authenticate user"""
        user = authenticate(
            username=attrs["email"],
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")
        attrs["user"] = user
        return attrs


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token serializer with user data"""

    def get_token(cls, user):
        """Override to add custom claims"""
        token = super().get_token(user)
        token["email"] = user.email
        token["role"] = user.role
        token["name"] = user.name
        return token

    @classmethod
    def get_token(cls, user):
        """Get tokens for user"""
        refresh = RefreshToken.for_user(user)
        refresh["email"] = user.email
        refresh["role"] = user.role
        refresh["name"] = user.name

        return refresh


class RefreshTokenSerializer(serializers.Serializer):
    """Refresh token serializer"""

    refresh = serializers.CharField()


class ChangePasswordSerializer(serializers.Serializer):
    """Change password serializer"""

    old_password = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    new_password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        """Validate passwords match and old password is correct"""
        if attrs["new_password"] != attrs.pop("new_password2"):
            raise serializers.ValidationError(
                {"new_password": "Passwords must match."}
            )
        return attrs

    def validate_old_password(self, value):
        """Validate old password"""
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class PasswordResetRequestSerializer(serializers.Serializer):
    """Request password reset"""

    email = serializers.EmailField()

    def validate_email(self, value):
        """Check if user exists"""
        try:
            User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("User with this email does not exist.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Confirm password reset"""

    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    new_password2 = serializers.CharField(
        write_only=True,
        required=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        """Validate passwords match"""
        if attrs["new_password"] != attrs.pop("new_password2"):
            raise serializers.ValidationError(
                {"new_password": "Passwords must match."}
            )
        return attrs


class EmailVerificationSerializer(serializers.Serializer):
    """Email verification serializer"""

    token = serializers.CharField()


class InstructorProfileSerializer(serializers.ModelSerializer):
    """Instructor profile serializer"""

    user = UserSerializer(read_only=True)

    class Meta:
        model = InstructorProfile
        fields = [
            "user",
            "bio",
            "website",
            "stripe_account_id",
            "stripe_onboarded",
            "is_approved",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "stripe_account_id",
            "stripe_onboarded",
            "is_approved",
            "created_at",
            "updated_at",
        ]


class CorporateManagerProfileSerializer(serializers.ModelSerializer):
    """Corporate manager profile serializer"""

    user = UserSerializer(read_only=True)

    class Meta:
        model = CorporateManagerProfile
        fields = ["user", "company_name", "team_size", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]
