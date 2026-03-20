"""
Integration tests: notifications API.

Covers notification templates, preferences, notification list, and log viewing.
"""

import pytest
import requests

from .conftest import api, TEST_RUN_ID

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Notification list (student's inbox)
# ---------------------------------------------------------------------------


def test_list_notifications_as_student(student_client):
    """GET /api/v1/notifications/ as student returns 200 (own notifications)."""
    resp = student_client.get("/api/v1/notifications/")
    assert resp.status_code == 200, (
        f"GET notifications returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, (list, dict)), (
        f"Unexpected response type for notifications: {type(data)}"
    )


def test_list_notifications_as_instructor(instructor_client):
    """GET /api/v1/notifications/ as instructor returns 200."""
    resp = instructor_client.get("/api/v1/notifications/")
    assert resp.status_code == 200, (
        f"GET notifications for instructor returned {resp.status_code}: {resp.text}"
    )


def test_list_notifications_unauthenticated():
    """GET /api/v1/notifications/ without auth must return 401."""
    resp = requests.get(api("/api/v1/notifications/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Notification templates
# ---------------------------------------------------------------------------


def test_list_notification_templates_as_instructor(instructor_client):
    """GET /api/v1/notifications/templates/ as instructor returns 200."""
    resp = instructor_client.get("/api/v1/notifications/templates/")
    assert resp.status_code == 200, (
        f"GET notification templates returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, (list, dict)), (
        f"Unexpected response type for templates: {type(data)}"
    )


def test_list_notification_templates_unauthenticated():
    """GET /api/v1/notifications/templates/ without auth must return 401."""
    resp = requests.get(api("/api/v1/notifications/templates/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


def test_create_notification_template_as_instructor(instructor_client):
    """POST /api/v1/notifications/templates/ as instructor creates a template."""
    resp = instructor_client.post(
        "/api/v1/notifications/templates/",
        json={
            "name": f"Welcome Template {TEST_RUN_ID}",
            "subject": "Welcome to the course!",
            "body": "Hi {{student_name}}, welcome to {{course_title}}.",
            "template_type": "enrollment",
        },
    )
    # 201 if created, 400 if duplicate name or bad data
    assert resp.status_code in (201, 400), (
        f"Unexpected status from template creation: {resp.status_code} — {resp.text}"
    )
    if resp.status_code == 201:
        data = resp.json()
        assert "id" in data, f"Missing 'id' in template response: {data}"


# ---------------------------------------------------------------------------
# Notification preferences
# ---------------------------------------------------------------------------


def test_list_notification_preferences_as_student(student_client):
    """GET /api/v1/notifications/preferences/my_preferences/ as student returns 200."""
    resp = student_client.get("/api/v1/notifications/preferences/my_preferences/")
    assert resp.status_code == 200, (
        f"GET notification preferences returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, (list, dict)), (
        f"Unexpected response type for preferences: {type(data)}"
    )


def test_list_notification_preferences_unauthenticated():
    """GET /api/v1/notifications/preferences/my_preferences/ without auth must return 401."""
    resp = requests.get(api("/api/v1/notifications/preferences/my_preferences/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Notification logs
# ---------------------------------------------------------------------------


def test_list_notification_logs_as_student(student_client):
    """GET /api/v1/notifications/logs/ as student returns 403 (admin-only endpoint)."""
    resp = student_client.get("/api/v1/notifications/logs/")
    assert resp.status_code == 403, (
        f"Expected 403 for student on admin-only logs, got {resp.status_code}: {resp.text}"
    )


def test_list_notification_logs_unauthenticated():
    """GET /api/v1/notifications/logs/ without auth must return 401."""
    resp = requests.get(api("/api/v1/notifications/logs/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )
