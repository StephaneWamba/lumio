"""Custom middleware for security headers and request observability."""

import time
import structlog

logger = structlog.get_logger(__name__)


class SecurityHeadersMiddleware:
    """Add hardened security headers to every response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Prevent MIME-type sniffing
        response["X-Content-Type-Options"] = "nosniff"

        # Deny embedding in iframes
        response["X-Frame-Options"] = "DENY"

        # Block XSS in legacy browsers
        response["X-XSS-Protection"] = "1; mode=block"

        # Don't send referrer outside origin
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=(self)"

        # CSP — tightened; static/media served from CloudFront only
        csp = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "media-src 'self' https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response["Content-Security-Policy"] = csp

        return response


class RequestLoggingMiddleware:
    """Log each request with duration, status, and user context (structlog)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start = time.monotonic()
        response = self.get_response(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        user_id = (
            request.user.id if hasattr(request, "user") and request.user.is_authenticated else None
        )

        logger.info(
            "http_request",
            method=request.method,
            path=request.path,
            status=response.status_code,
            duration_ms=duration_ms,
            user_id=user_id,
            ip=_get_client_ip(request),
        )
        return response


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
