"""Test settings"""
from .base import *  # noqa

DEBUG = True
ENVIRONMENT = "test"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": ":memory:",
    }
}

# Use in-memory cache for tests
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Celery eager for tests
CELERY_TASK_ALWAYS_EAGER = True

# Disable Sentry for tests
SENTRY_DSN = ""

# Email backend
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Disable HTTPS redirects in tests
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
