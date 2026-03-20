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

# Disable throttling in development — keep rate keys to avoid ImproperlyConfigured
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
