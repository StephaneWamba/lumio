"""
Integration tests: analytics API.

Covers course analytics, lesson analytics, quiz analytics, progress snapshots,
and engagement metrics. Analytics are instructor-only — students get 403
(empty queryset returns no results, but list itself succeeds; permission
enforcement is at the queryset level returning .none() for students).
"""

import pytest
import requests

from .conftest import api

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Course analytics
# ---------------------------------------------------------------------------


def test_list_course_analytics_as_instructor(instructor_client):
    """GET /api/v1/analytics/courses/ as instructor returns 200."""
    resp = instructor_client.get("/api/v1/analytics/courses/")
    assert resp.status_code == 200, (
        f"GET course analytics returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, (list, dict)), (
        f"Unexpected response type for course analytics: {type(data)}"
    )


def test_list_course_analytics_as_student(student_client):
    """GET /api/v1/analytics/courses/ as student returns 200 with empty results.

    The CourseAnalyticsViewSet returns .none() for students (not 403),
    so the call succeeds but yields an empty list.
    """
    resp = student_client.get("/api/v1/analytics/courses/")
    assert resp.status_code == 200, (
        f"GET course analytics for student returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    # Students see nothing
    assert items == [], (
        f"Expected empty analytics list for student, got: {items}"
    )


def test_list_course_analytics_unauthenticated():
    """GET /api/v1/analytics/courses/ without auth must return 401."""
    resp = requests.get(api("/api/v1/analytics/courses/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Lesson analytics
# ---------------------------------------------------------------------------


def test_list_lesson_analytics_as_instructor(instructor_client):
    """GET /api/v1/analytics/lessons/ as instructor returns 200."""
    resp = instructor_client.get("/api/v1/analytics/lessons/")
    assert resp.status_code == 200, (
        f"GET lesson analytics returned {resp.status_code}: {resp.text}"
    )


def test_list_lesson_analytics_as_student_empty(student_client):
    """GET /api/v1/analytics/lessons/ as student returns 200 with empty list."""
    resp = student_client.get("/api/v1/analytics/lessons/")
    assert resp.status_code == 200, (
        f"GET lesson analytics for student returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert items == [], f"Expected empty lesson analytics for student, got: {items}"


# ---------------------------------------------------------------------------
# Quiz analytics
# ---------------------------------------------------------------------------


def test_list_quiz_analytics_as_instructor(instructor_client):
    """GET /api/v1/analytics/quizzes/ as instructor returns 200."""
    resp = instructor_client.get("/api/v1/analytics/quizzes/")
    assert resp.status_code == 200, (
        f"GET quiz analytics returned {resp.status_code}: {resp.text}"
    )


def test_list_quiz_analytics_as_student_empty(student_client):
    """GET /api/v1/analytics/quizzes/ as student returns 200 with empty list."""
    resp = student_client.get("/api/v1/analytics/quizzes/")
    assert resp.status_code == 200, (
        f"GET quiz analytics for student returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert items == [], f"Expected empty quiz analytics for student, got: {items}"


# ---------------------------------------------------------------------------
# Progress snapshots
# ---------------------------------------------------------------------------


def test_list_progress_snapshots_as_instructor(instructor_client):
    """GET /api/v1/analytics/progress-snapshots/ as instructor returns 200."""
    resp = instructor_client.get("/api/v1/analytics/progress-snapshots/")
    assert resp.status_code == 200, (
        f"GET progress snapshots returned {resp.status_code}: {resp.text}"
    )


def test_list_progress_snapshots_as_student(student_client):
    """GET /api/v1/analytics/progress-snapshots/ as student returns 200 (own snapshots)."""
    resp = student_client.get("/api/v1/analytics/progress-snapshots/")
    assert resp.status_code == 200, (
        f"GET progress snapshots for student returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    # May be empty for a new student — just check it's a list
    assert isinstance(items, list), f"Expected list of snapshots: {type(items)}"


# ---------------------------------------------------------------------------
# Engagement metrics
# ---------------------------------------------------------------------------


def test_list_engagement_metrics_as_instructor(instructor_client):
    """GET /api/v1/analytics/engagement/ as instructor returns 200."""
    resp = instructor_client.get("/api/v1/analytics/engagement/")
    assert resp.status_code == 200, (
        f"GET engagement metrics returned {resp.status_code}: {resp.text}"
    )


def test_list_engagement_metrics_as_student_empty(student_client):
    """GET /api/v1/analytics/engagement/ as student returns 200 with empty list."""
    resp = student_client.get("/api/v1/analytics/engagement/")
    assert resp.status_code == 200, (
        f"GET engagement metrics for student returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert items == [], f"Expected empty engagement metrics for student, got: {items}"


def test_list_engagement_metrics_unauthenticated():
    """GET /api/v1/analytics/engagement/ without auth must return 401."""
    resp = requests.get(api("/api/v1/analytics/engagement/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Analytics actions
# ---------------------------------------------------------------------------


def test_progress_snapshot_student_snapshots_requires_enrollment_id(student_client):
    """GET /api/v1/analytics/progress-snapshots/student_snapshots/ without enrollment_id → 400."""
    resp = student_client.get("/api/v1/analytics/progress-snapshots/student_snapshots/")
    assert resp.status_code == 400, (
        f"Expected 400 for missing enrollment_id, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "enrollment_id" in str(data).lower() or "detail" in data, (
        f"Expected informative error about enrollment_id: {data}"
    )


def test_engagement_top_students_requires_course_id(instructor_client):
    """GET /api/v1/analytics/engagement/top_engaged_students/ without course_id → 400."""
    resp = instructor_client.get(
        "/api/v1/analytics/engagement/top_engaged_students/"
    )
    assert resp.status_code == 400, (
        f"Expected 400 for missing course_id, got {resp.status_code}: {resp.text}"
    )


def test_engagement_by_type_requires_course_id(instructor_client):
    """GET /api/v1/analytics/engagement/engagement_by_type/ without course_id → 400."""
    resp = instructor_client.get(
        "/api/v1/analytics/engagement/engagement_by_type/"
    )
    assert resp.status_code == 400, (
        f"Expected 400 for missing course_id, got {resp.status_code}: {resp.text}"
    )
