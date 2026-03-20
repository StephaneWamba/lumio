"""
Integration tests: authentication and user profile flow.

Covers registration, login, token refresh, profile read/update, and
password change against the live API.
"""

import pytest
import requests
from uuid import uuid4

from .conftest import api, TEST_RUN_ID, AuthedClient, get_token

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def test_register_student():
    """POST /api/v1/auth/register/ with valid data returns 201 with user fields."""
    unique = uuid4().hex[:6]
    resp = requests.post(
        api("/api/v1/auth/register/"),
        json={
            "email": f"new_student_{unique}_{TEST_RUN_ID}@test.lumio.io",
            "password": f"ValidPass_{unique}!",
            "password2": f"ValidPass_{unique}!",
            "name": f"New Student {unique}",
            "role": "student",
        },
        timeout=30,
    )
    assert resp.status_code == 201, (
        f"Expected 201, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    # The register endpoint wraps user in {"message": "...", "user": {...}}
    user = data.get("user", data)
    assert "id" in user, f"Missing 'id' in register response user: {data}"
    assert "email" in user, f"Missing 'email' in register response user: {data}"
    assert "role" in user, f"Missing 'role' in register response user: {data}"
    assert user["role"] == "student", f"Expected role='student', got: {user['role']}"


def test_register_instructor():
    """POST /api/v1/auth/register/ with role=instructor returns 201."""
    unique = uuid4().hex[:6]
    resp = requests.post(
        api("/api/v1/auth/register/"),
        json={
            "email": f"new_instr_{unique}_{TEST_RUN_ID}@test.lumio.io",
            "password": f"ValidPass_{unique}!",
            "password2": f"ValidPass_{unique}!",
            "name": f"New Instructor {unique}",
            "role": "instructor",
        },
        timeout=30,
    )
    assert resp.status_code == 201, (
        f"Expected 201, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    user = data.get("user", data)
    assert user.get("role") == "instructor", (
        f"Expected role='instructor', got: {user.get('role')} — full response: {data}"
    )


def test_register_duplicate_email(student_credentials):
    """Registering the same email a second time must return 400."""
    resp = requests.post(
        api("/api/v1/auth/register/"),
        json={
            "email": student_credentials["email"],
            "password": student_credentials["password"],
            "password2": student_credentials["password"],
            "name": "Duplicate Student",
            "role": "student",
        },
        timeout=30,
    )
    assert resp.status_code == 400, (
        f"Expected 400 for duplicate email, got {resp.status_code}: {resp.text}"
    )


def test_register_invalid_email():
    """POST with a malformed email must return 400."""
    resp = requests.post(
        api("/api/v1/auth/register/"),
        json={
            "email": "not-an-email",
            "password": "ValidPass123!",
            "name": "Bad Email User",
            "role": "student",
        },
        timeout=30,
    )
    assert resp.status_code == 400, (
        f"Expected 400 for invalid email, got {resp.status_code}: {resp.text}"
    )


def test_register_missing_password():
    """POST without a password must return 400."""
    unique = uuid4().hex[:6]
    resp = requests.post(
        api("/api/v1/auth/register/"),
        json={
            "email": f"nopwd_{unique}@test.lumio.io",
            "name": "No Password",
            "role": "student",
        },
        timeout=30,
    )
    assert resp.status_code in (400, 429), (
        f"Expected 400 for missing password, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


def test_login_success(student_credentials):
    """POST /api/v1/auth/login/ with valid credentials returns 200 with tokens."""
    resp = requests.post(
        api("/api/v1/auth/login/"),
        json={
            "email": student_credentials["email"],
            "password": student_credentials["password"],
        },
        timeout=30,
    )
    assert resp.status_code == 200, (
        f"Login failed: status={resp.status_code} body={resp.text}"
    )
    data = resp.json()
    assert "access" in data, f"Missing 'access' token in login response: {data}"
    assert "refresh" in data, f"Missing 'refresh' token in login response: {data}"
    assert "user" in data, f"Missing 'user' object in login response: {data}"
    # Tokens must be non-empty strings
    assert isinstance(data["access"], str) and len(data["access"]) > 20, (
        f"Access token looks invalid: {data['access']}"
    )
    assert isinstance(data["refresh"], str) and len(data["refresh"]) > 20, (
        f"Refresh token looks invalid: {data['refresh']}"
    )


def test_login_wrong_password(student_credentials):
    """POST with wrong password must return 401."""
    resp = requests.post(
        api("/api/v1/auth/login/"),
        json={
            "email": student_credentials["email"],
            "password": "completely_wrong_password_xyz",
        },
        timeout=30,
    )
    assert resp.status_code in (400, 401), (
        f"Expected 400 or 401 for wrong password, got {resp.status_code}: {resp.text}"
    )


def test_login_nonexistent_user():
    """POST with email that does not exist must return 400 or 401."""
    resp = requests.post(
        api("/api/v1/auth/login/"),
        json={
            "email": f"ghost_{uuid4().hex}@test.lumio.io",
            "password": "AnyPassword123!",
        },
        timeout=30,
    )
    assert resp.status_code in (400, 401), (
        f"Expected 400 or 401 for nonexistent user, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


def test_token_refresh(student_refresh_token):
    """POST /api/v1/auth/refresh/ with a valid refresh token returns a new access token."""
    resp = requests.post(
        api("/api/v1/auth/refresh/"),
        json={"refresh": student_refresh_token},
        timeout=30,
    )
    assert resp.status_code == 200, (
        f"Token refresh failed: status={resp.status_code} body={resp.text}"
    )
    data = resp.json()
    assert "access" in data, f"Missing 'access' in refresh response: {data}"
    assert isinstance(data["access"], str) and len(data["access"]) > 20, (
        f"Refreshed access token looks invalid: {data['access']}"
    )


def test_token_refresh_invalid():
    """POST /api/v1/auth/refresh/ with a bogus token must return 401."""
    resp = requests.post(
        api("/api/v1/auth/refresh/"),
        json={"refresh": "this.is.not.a.real.token"},
        timeout=30,
    )
    assert resp.status_code in (400, 401), (
        f"Expected 400/401 for invalid refresh token, got {resp.status_code}: {resp.text}"
    )


def test_token_refresh_missing_field():
    """POST /api/v1/auth/refresh/ with no refresh field must return 400."""
    resp = requests.post(
        api("/api/v1/auth/refresh/"),
        json={},
        timeout=30,
    )
    assert resp.status_code == 400, (
        f"Expected 400 for missing refresh field, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


def test_get_profile(student_client, student_credentials):
    """GET /api/v1/auth/users/me/ returns the authenticated user's data."""
    resp = student_client.get("/api/v1/auth/users/me/")
    assert resp.status_code == 200, (
        f"GET profile failed: status={resp.status_code} body={resp.text}"
    )
    data = resp.json()
    assert "id" in data, f"Missing 'id' in profile response: {data}"
    assert "email" in data, f"Missing 'email' in profile response: {data}"
    assert data["email"] == student_credentials["email"], (
        f"Expected email={student_credentials['email']}, got: {data['email']}"
    )


def test_get_profile_unauthenticated():
    """GET /api/v1/auth/users/me/ without a token must return 401."""
    resp = requests.get(api("/api/v1/auth/users/me/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated profile access, got {resp.status_code}: {resp.text}"
    )


def test_update_profile(student_client):
    """PATCH /api/v1/auth/users/update_profile/ updates the user's name."""
    new_name = f"Updated Student {TEST_RUN_ID}"
    resp = student_client.patch(
        "/api/v1/auth/users/update_profile/",
        json={"name": new_name},
    )
    assert resp.status_code == 200, (
        f"PATCH profile failed: status={resp.status_code} body={resp.text}"
    )
    data = resp.json()
    assert data.get("name") == new_name, (
        f"Expected updated name='{new_name}', got: {data.get('name')} — full: {data}"
    )


# ---------------------------------------------------------------------------
# Password change
# ---------------------------------------------------------------------------


def test_change_password(student_client, student_credentials):
    """POST /api/v1/auth/users/change_password/ with correct old password succeeds."""
    old_password = student_credentials["password"]
    new_password = f"NewPass_{TEST_RUN_ID}_X!"

    resp = student_client.post(
        "/api/v1/auth/users/change_password/",
        json={
            "old_password": old_password,
            "new_password": new_password,
            "new_password2": new_password,
        },
    )
    assert resp.status_code == 200, (
        f"change_password failed: status={resp.status_code} body={resp.text}"
    )
    data = resp.json()
    assert "message" in data, f"Expected 'message' in change_password response: {data}"

    # Restore the original password so other session fixtures keep working
    restore_resp = student_client.post(
        "/api/v1/auth/users/change_password/",
        json={
            "old_password": new_password,
            "new_password": old_password,
            "new_password2": old_password,
        },
    )
    assert restore_resp.status_code == 200, (
        f"Password restore after test failed: status={restore_resp.status_code} "
        f"body={restore_resp.text}"
    )


def test_change_password_wrong_old(student_client):
    """POST change_password with incorrect old password must return 400."""
    resp = student_client.post(
        "/api/v1/auth/users/change_password/",
        json={
            "old_password": "this_is_wrong_old_password",
            "new_password": "AnyNewPass123!",
        },
    )
    assert resp.status_code == 400, (
        f"Expected 400 for wrong old password, got {resp.status_code}: {resp.text}"
    )
