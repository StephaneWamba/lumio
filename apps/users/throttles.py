"""Custom DRF throttle classes for sensitive auth endpoints."""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class AuthLoginThrottle(AnonRateThrottle):
    """5 login attempts per minute per IP — brute-force protection."""

    scope = "auth_login"


class AuthRegisterThrottle(AnonRateThrottle):
    """10 registration attempts per hour per IP."""

    scope = "auth_register"


class PasswordResetThrottle(AnonRateThrottle):
    """3 password reset requests per hour per IP."""

    scope = "password_reset"


class TokenRefreshThrottle(UserRateThrottle):
    """30 token refresh calls per hour per authenticated user."""

    scope = "token_refresh"


class PresignedUrlThrottle(UserRateThrottle):
    """20 presigned URL requests per minute per user — upload-rate guard."""

    scope = "presigned_url"


class QuizSubmitThrottle(UserRateThrottle):
    """60 quiz submissions per hour per user."""

    scope = "quiz_submit"
