"""Development settings"""
from .base import *  # noqa

DEBUG = True
ENVIRONMENT = "development"

# Disable CORS restrictions in development
CORS_ALLOW_ALL_ORIGINS = True

# Allow all hosts
ALLOWED_HOSTS = ["*"]

# Celery in eager mode for development
CELERY_TASK_ALWAYS_EAGER = True

# Dummy cache backend for development
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

# Email backend
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Don't verify Sentry
SENTRY_DSN = ""
