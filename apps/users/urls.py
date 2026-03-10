"""Users app URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    RegisterView,
    LoginView,
    RefreshTokenView,
    CustomTokenObtainPairView,
    PasswordResetRequestView,
    PasswordResetConfirmView,
    EmailVerificationView,
    UserViewSet,
    InstructorProfileViewSet,
    CorporateManagerProfileViewSet,
)

router = DefaultRouter()
router.register(r"users", UserViewSet, basename="user")
router.register(r"instructor-profiles", InstructorProfileViewSet, basename="instructor-profile")
router.register(r"corporate-profiles", CorporateManagerProfileViewSet, basename="corporate-profile")

urlpatterns = [
    # JWT Authentication
    path("token/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Auth endpoints
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("refresh/", RefreshTokenView.as_view(), name="refresh"),
    # Password reset
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset_request"),
    path(
        "password-reset-confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"
    ),
    # Email verification
    path("verify-email/", EmailVerificationView.as_view(), name="verify_email"),
    # Routers
    path("", include(router.urls)),
]
