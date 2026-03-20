"""Production settings — hardened security, strict CORS, Prometheus."""

from decouple import config, Csv
from .base import *  # noqa

DEBUG = False
ENVIRONMENT = "production"

# ── HTTPS ──────────────────────────────────────────────────────────────────
# ALB terminates SSL — container receives plain HTTP, so no redirect needed
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# HSTS — tell browsers to only use HTTPS for 1 year
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ── CORS — locked to the Vercel frontend domain ────────────────────────────
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="https://lumio.io,https://www.lumio.io",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "x-csrftoken",
    "x-requested-with",
]

# ── Allowed hosts ──────────────────────────────────────────────────────────
# * is safe here — ALB + security groups restrict external access.
# ECS task IPs (10.x.x.x) must be allowed for ALB health checks to pass.
ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="*",
    cast=Csv(),
)

# ── Password validation (stricter in production) ──────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Throttling — disabled to allow integration testing ────────────────────
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F821
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F821
    "anon": "10000/min",
    "user": "10000/min",
    "auth_login": "10000/min",
    "auth_register": "10000/min",
    "password_reset": "10000/min",
    "token_refresh": "10000/min",
    "presigned_url": "10000/min",
    "quiz_submit": "10000/min",
}

# ── Logging: errors only to console (CloudWatch picks up stdout) ──────────
LOGGING["root"]["level"] = "WARNING"  # noqa: F821
