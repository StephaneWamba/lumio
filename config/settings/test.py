"""Test settings"""

from .base import *  # noqa

DEBUG = True
ENVIRONMENT = "test"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="lumio_test"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default="postgres"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
        "TEST": {"NAME": config("DB_NAME", default="lumio_test")},
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
