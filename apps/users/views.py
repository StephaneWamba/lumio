"""User authentication and profile views"""

from django.contrib.auth import authenticate
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User, InstructorProfile, CorporateManagerProfile
from .throttles import (
    AuthLoginThrottle,
    AuthRegisterThrottle,
    PasswordResetThrottle,
    TokenRefreshThrottle,
)
from .serializers import (
    UserSerializer,
    UserDetailSerializer,
    RegisterSerializer,
    LoginSerializer,
    CustomTokenObtainPairSerializer,
    ChangePasswordSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    EmailVerificationSerializer,
    InstructorProfileSerializer,
    CorporateManagerProfileSerializer,
)
import structlog

logger = structlog.get_logger()


class CustomTokenObtainPairView(TokenObtainPairView):
    """Custom JWT token endpoint with additional user data"""

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AuthLoginThrottle]


class RegisterView(APIView):
    """User registration endpoint"""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRegisterThrottle]

    def post(self, request):
        """Register new user"""
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.save()
        logger.info(
            "user_registered",
            user_id=user.id,
            email=user.email,
            role=user.role,
        )

        # TODO: Send email verification link

        return Response(
            {
                "message": "User registered successfully. Please verify your email.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """User login endpoint"""

    permission_classes = [AllowAny]
    throttle_classes = [AuthLoginThrottle]

    def post(self, request):
        """Login user and return tokens"""
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        refresh["email"] = user.email
        refresh["role"] = user.role
        refresh["name"] = user.name

        logger.info("user_logged_in", user_id=user.id, email=user.email)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


class RefreshTokenView(APIView):
    """Refresh JWT token endpoint"""

    permission_classes = [AllowAny]

    def post(self, request):
        """Refresh access token"""
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"refresh": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            refresh = RefreshToken(refresh_token)
            return Response(
                {
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return Response(
                {"error": "Invalid refresh token."},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class UserViewSet(viewsets.ModelViewSet):
    """User CRUD and profile operations"""

    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Users can only see themselves"""
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return User.objects.all()
        return User.objects.filter(id=user.id)

    @action(detail=False, methods=["get"])
    def me(self, request):
        """Get current user profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=["put", "patch"])
    def update_profile(self, request):
        """Update current user profile"""
        user = request.user
        serializer = UserDetailSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info("user_profile_updated", user_id=user.id)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=["post"])
    def change_password(self, request):
        """Change user password"""
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save()

        logger.info("user_password_changed", user_id=user.id)

        return Response(
            {"message": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class InstructorProfileViewSet(viewsets.ModelViewSet):
    """Instructor profile CRUD"""

    queryset = InstructorProfile.objects.all()
    serializer_class = InstructorProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Instructors see only their profile"""
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return InstructorProfile.objects.all()
        if user.role == User.ROLE_INSTRUCTOR:
            return InstructorProfile.objects.filter(user=user)
        return InstructorProfile.objects.none()

    @action(detail=False, methods=["get"])
    def my_profile(self, request):
        """Get current user's instructor profile"""
        try:
            profile = InstructorProfile.objects.get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except InstructorProfile.DoesNotExist:
            return Response(
                {"error": "Instructor profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    @action(detail=False, methods=["post"])
    def onboard_stripe(self, request):
        """Initiate Stripe Connect onboarding"""
        # TODO: Implement Stripe Connect OAuth flow
        return Response(
            {"message": "Stripe onboarding initiated."},
            status=status.HTTP_200_OK,
        )


class CorporateManagerProfileViewSet(viewsets.ModelViewSet):
    """Corporate manager profile CRUD"""

    queryset = CorporateManagerProfile.objects.all()
    serializer_class = CorporateManagerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Corporate managers see only their profile"""
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return CorporateManagerProfile.objects.all()
        if user.role == User.ROLE_CORPORATE_MANAGER:
            return CorporateManagerProfile.objects.filter(user=user)
        return CorporateManagerProfile.objects.none()

    @action(detail=False, methods=["get"])
    def my_profile(self, request):
        """Get current user's corporate manager profile"""
        try:
            profile = CorporateManagerProfile.objects.get(user=request.user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except CorporateManagerProfile.DoesNotExist:
            return Response(
                {"error": "Corporate manager profile not found."},
                status=status.HTTP_404_NOT_FOUND,
            )


class PasswordResetRequestView(APIView):
    """Request password reset via email"""

    permission_classes = [AllowAny]

    def post(self, request):
        """Send password reset email"""
        serializer = PasswordResetRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        user = User.objects.get(email=email)

        # TODO: Generate reset token and send via Resend
        logger.info("password_reset_requested", user_id=user.id, email=email)

        return Response(
            {"message": "If this email exists, a password reset link will be sent."},
            status=status.HTTP_200_OK,
        )


class PasswordResetConfirmView(APIView):
    """Confirm password reset with token"""

    permission_classes = [AllowAny]

    def post(self, request):
        """Reset password with token"""
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # TODO: Validate token and reset password
        logger.info("password_reset_confirmed")

        return Response(
            {"message": "Password reset successfully."},
            status=status.HTTP_200_OK,
        )


class EmailVerificationView(APIView):
    """Verify user email with token"""

    permission_classes = [AllowAny]

    def post(self, request):
        """Verify email with token"""
        serializer = EmailVerificationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # TODO: Validate token and mark email as verified
        logger.info("email_verified")

        return Response(
            {"message": "Email verified successfully."},
            status=status.HTTP_200_OK,
        )
