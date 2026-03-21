"""Redis-backed token store for email verification and password reset."""

import secrets

from django.core.cache import cache

# TTLs in seconds
_TTL = {
    "email_verify": 24 * 60 * 60,  # 24 hours
    "password_reset": 60 * 60,  # 1 hour
}

_PREFIX = "auth_token"


def generate_token(purpose: str, user_id: int) -> str:
    """Generate a secure random token, store it in Redis, and return it."""
    token = secrets.token_urlsafe(32)
    ttl = _TTL[purpose]
    cache.set(f"{_PREFIX}:{purpose}:{token}", user_id, timeout=ttl)
    return token


def validate_token(purpose: str, token: str) -> int | None:
    """Return user_id if token is valid, else None. Does NOT consume the token."""
    return cache.get(f"{_PREFIX}:{purpose}:{token}")


def consume_token(purpose: str, token: str) -> int | None:
    """Validate and atomically delete token. Returns user_id or None."""
    key = f"{_PREFIX}:{purpose}:{token}"
    return cache.get_and_delete(key)
