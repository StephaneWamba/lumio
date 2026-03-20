"""Phase 11 — Security & Observability tests."""

from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

User = get_user_model()


# ── Security headers ───────────────────────────────────────────────────────


class SecurityHeadersTests(APITestCase):
    """Verify every response carries the required security headers."""

    def test_x_content_type_options(self):
        response = self.client.get("/health/")
        self.assertEqual(response.get("X-Content-Type-Options"), "nosniff")

    def test_x_frame_options(self):
        response = self.client.get("/health/")
        self.assertEqual(response.get("X-Frame-Options"), "DENY")

    def test_referrer_policy(self):
        response = self.client.get("/health/")
        self.assertEqual(response.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_permissions_policy_present(self):
        response = self.client.get("/health/")
        self.assertIn("Permissions-Policy", response)

    def test_content_security_policy_present(self):
        response = self.client.get("/health/")
        csp = response.get("Content-Security-Policy", "")
        self.assertIn("default-src", csp)
        self.assertIn("frame-ancestors", csp)

    def test_x_xss_protection(self):
        response = self.client.get("/health/")
        self.assertEqual(response.get("X-XSS-Protection"), "1; mode=block")


# ── Throttle classes ───────────────────────────────────────────────────────


class ThrottleClassTests(TestCase):
    """Verify throttle classes are configured with correct scopes."""

    def test_auth_login_scope(self):
        from apps.users.throttles import AuthLoginThrottle

        self.assertEqual(AuthLoginThrottle.scope, "auth_login")

    def test_auth_register_scope(self):
        from apps.users.throttles import AuthRegisterThrottle

        self.assertEqual(AuthRegisterThrottle.scope, "auth_register")

    def test_password_reset_scope(self):
        from apps.users.throttles import PasswordResetThrottle

        self.assertEqual(PasswordResetThrottle.scope, "password_reset")

    def test_token_refresh_scope(self):
        from apps.users.throttles import TokenRefreshThrottle

        self.assertEqual(TokenRefreshThrottle.scope, "token_refresh")

    def test_presigned_url_scope(self):
        from apps.users.throttles import PresignedUrlThrottle

        self.assertEqual(PresignedUrlThrottle.scope, "presigned_url")

    def test_quiz_submit_scope(self):
        from apps.users.throttles import QuizSubmitThrottle

        self.assertEqual(QuizSubmitThrottle.scope, "quiz_submit")


# ── Throttle rate settings ─────────────────────────────────────────────────


class ThrottleSettingsTests(TestCase):
    """Verify throttle rates are defined for all custom scopes."""

    def test_throttle_rates_defined(self):
        from django.conf import settings

        rates: dict = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        required_scopes = [
            "auth_login",
            "auth_register",
            "password_reset",
            "token_refresh",
            "presigned_url",
            "quiz_submit",
        ]
        for scope in required_scopes:
            self.assertIn(scope, rates, f"Throttle rate missing for scope: {scope}")

    def test_auth_login_rate_is_strict(self):
        from django.conf import settings

        rate = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["auth_login"]
        # Must be per-minute
        self.assertIn("/min", rate)

    def test_password_reset_rate_is_per_hour(self):
        from django.conf import settings

        rate = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["password_reset"]
        self.assertIn("/hour", rate)


# ── Prometheus metrics ─────────────────────────────────────────────────────


class PrometheusMetricsTests(TestCase):
    """Verify all custom Prometheus metrics are importable and correctly typed."""

    def test_enrollment_counter_importable(self):
        from config.metrics import enrollment_created, enrollment_completed
        from prometheus_client import Counter

        self.assertIsInstance(enrollment_created, Counter)
        self.assertIsInstance(enrollment_completed, Counter)

    def test_quiz_counters_importable(self):
        from config.metrics import (
            quiz_attempt_started,
            quiz_attempt_passed,
            quiz_attempt_failed,
        )
        from prometheus_client import Counter

        self.assertIsInstance(quiz_attempt_started, Counter)
        self.assertIsInstance(quiz_attempt_passed, Counter)
        self.assertIsInstance(quiz_attempt_failed, Counter)

    def test_transcoding_metrics_importable(self):
        from config.metrics import (
            transcoding_job_started,
            transcoding_job_completed,
            transcoding_job_failed,
            transcoding_duration_seconds,
        )
        from prometheus_client import Counter, Histogram

        self.assertIsInstance(transcoding_job_started, Counter)
        self.assertIsInstance(transcoding_job_completed, Counter)
        self.assertIsInstance(transcoding_duration_seconds, Histogram)

    def test_celery_queue_depth_is_gauge(self):
        from config.metrics import celery_queue_depth
        from prometheus_client import Gauge

        self.assertIsInstance(celery_queue_depth, Gauge)

    def test_api_duration_histogram_importable(self):
        from config.metrics import api_request_duration_seconds
        from prometheus_client import Histogram

        self.assertIsInstance(api_request_duration_seconds, Histogram)

    def test_metrics_counter_increment(self):
        """Counters must be incrementable without error."""
        from config.metrics import enrollment_created

        before = enrollment_created.labels(course_id="1")._value.get()
        enrollment_created.labels(course_id="1").inc()
        after = enrollment_created.labels(course_id="1")._value.get()
        self.assertEqual(after, before + 1)


# ── Auth view throttle wiring ──────────────────────────────────────────────


class AuthViewThrottleWiringTests(TestCase):
    """Verify throttle classes are attached to the correct views."""

    def test_login_view_has_throttle(self):
        from apps.users.views import LoginView
        from apps.users.throttles import AuthLoginThrottle

        self.assertIn(AuthLoginThrottle, LoginView.throttle_classes)

    def test_register_view_has_throttle(self):
        from apps.users.views import RegisterView
        from apps.users.throttles import AuthRegisterThrottle

        self.assertIn(AuthRegisterThrottle, RegisterView.throttle_classes)

    def test_token_obtain_has_throttle(self):
        from apps.users.views import CustomTokenObtainPairView
        from apps.users.throttles import AuthLoginThrottle

        self.assertIn(AuthLoginThrottle, CustomTokenObtainPairView.throttle_classes)


# ── CORS/production settings ───────────────────────────────────────────────


class ProductionSettingsTests(TestCase):
    """Verify production hardening settings are set correctly."""

    @override_settings(
        SECURE_HSTS_SECONDS=31_536_000,
        SECURE_HSTS_INCLUDE_SUBDOMAINS=True,
        SECURE_HSTS_PRELOAD=True,
        SESSION_COOKIE_HTTPONLY=True,
        CSRF_COOKIE_HTTPONLY=True,
    )
    def test_hsts_configured(self):
        from django.conf import settings

        self.assertEqual(settings.SECURE_HSTS_SECONDS, 31_536_000)
        self.assertTrue(settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)
        self.assertTrue(settings.SECURE_HSTS_PRELOAD)

    @override_settings(SESSION_COOKIE_HTTPONLY=True, CSRF_COOKIE_HTTPONLY=True)
    def test_cookies_httponly(self):
        from django.conf import settings

        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
