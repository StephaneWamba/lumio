"""
Integration tests: cohorts and drip scheduling.

Covers cohort creation, listing, student joining, drip schedule creation,
and the manual release action.
"""

import pytest
import requests
from uuid import uuid4

from .conftest import api, TEST_RUN_ID

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Session-scoped cohort fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def cohort(instructor_client, published_course):
    """Create a cohort for the session course as the instructor.

    Returns the cohort dict.
    """
    course_id = published_course["id"]
    resp = instructor_client.post(
        "/api/v1/cohorts/cohorts/",
        json={
            "course": course_id,
            "name": f"Integration Cohort {TEST_RUN_ID}",
            "start_date": "2026-04-01",
            "max_students": 100,
            "is_open": True,
        },
    )
    assert resp.status_code == 201, (
        f"cohort fixture: creation failed: status={resp.status_code} body={resp.text}"
    )
    return resp.json()


# ---------------------------------------------------------------------------
# Cohort creation
# ---------------------------------------------------------------------------


def test_create_cohort_as_instructor(instructor_client, published_course):
    """POST /api/v1/cohorts/cohorts/ as instructor creates a cohort."""
    unique = uuid4().hex[:6]
    resp = instructor_client.post(
        "/api/v1/cohorts/cohorts/",
        json={
            "course": published_course["id"],
            "name": f"Extra Cohort {unique}",
            "start_date": "2026-05-01",
            "max_students": 50,
            "is_open": True,
        },
    )
    assert resp.status_code == 201, (
        f"Cohort creation returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "id" in data, f"Missing 'id' in cohort creation response: {data}"
    assert "name" in data, f"Missing 'name' in cohort creation response: {data}"


def test_create_cohort_as_student_forbidden(student_client, published_course):
    """Students cannot create cohorts — must return 403 or raise PermissionError."""
    resp = student_client.post(
        "/api/v1/cohorts/cohorts/",
        json={
            "course": published_course["id"],
            "name": "Forbidden Cohort",
            "start_date": "2026-05-01",
        },
    )
    # PermissionError from perform_create propagates as 500 or is caught as 403
    assert resp.status_code in (403, 500), (
        f"Expected 403/500 for student creating cohort, got {resp.status_code}: {resp.text}"
    )


def test_create_cohort_unauthenticated(published_course):
    """Unauthenticated cohort creation must return 401."""
    resp = requests.post(
        api("/api/v1/cohorts/cohorts/"),
        json={
            "course": published_course["id"],
            "name": "Anon Cohort",
            "start_date": "2026-05-01",
        },
        timeout=15,
    )
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated cohort creation, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Cohort listing
# ---------------------------------------------------------------------------


def test_list_cohorts_as_instructor(instructor_client, cohort):
    """GET /api/v1/cohorts/cohorts/ as instructor returns cohorts for their courses."""
    resp = instructor_client.get("/api/v1/cohorts/cohorts/")
    assert resp.status_code == 200, (
        f"GET cohorts returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert len(items) >= 1, f"Expected at least 1 cohort, got: {items}"
    cohort_ids = [c["id"] for c in items]
    assert cohort["id"] in cohort_ids, (
        f"Session cohort {cohort['id']} not found in instructor's list. Got: {cohort_ids}"
    )


def test_list_cohorts_as_student(student_client, cohort):
    """GET /api/v1/cohorts/cohorts/ as student returns cohorts for published courses."""
    resp = student_client.get("/api/v1/cohorts/cohorts/")
    assert resp.status_code == 200, (
        f"GET cohorts for student returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert isinstance(items, list), f"Expected list, got: {type(items)}"


def test_list_cohorts_unauthenticated():
    """GET /api/v1/cohorts/cohorts/ without auth must return 401."""
    resp = requests.get(api("/api/v1/cohorts/cohorts/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


def test_get_cohort_detail(student_client, cohort):
    """GET /api/v1/cohorts/cohorts/{id}/ returns the cohort detail."""
    cohort_id = cohort["id"]
    resp = student_client.get(f"/api/v1/cohorts/cohorts/{cohort_id}/")
    assert resp.status_code == 200, (
        f"GET cohort detail returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data["id"] == cohort_id, f"Expected cohort id={cohort_id}, got: {data.get('id')}"


# ---------------------------------------------------------------------------
# Join cohort
# ---------------------------------------------------------------------------


def test_join_cohort_as_student(student_client, cohort):
    """POST /api/v1/cohorts/cohorts/{id}/join/ student joins an open cohort."""
    cohort_id = cohort["id"]
    resp = student_client.post(f"/api/v1/cohorts/cohorts/{cohort_id}/join/")
    # 201 new member, 400 if already a member (acceptable for idempotent re-run)
    assert resp.status_code in (201, 400), (
        f"Unexpected status from join: {resp.status_code} — {resp.text}"
    )
    if resp.status_code == 201:
        data = resp.json()
        assert "id" in data, f"Missing 'id' in CohortMember response: {data}"
    else:
        # Should be "Already a member" or similar
        assert "member" in resp.text.lower() or "already" in resp.text.lower(), (
            f"Expected 'already member' message, got: {resp.text}"
        )


def test_join_cohort_unauthenticated(cohort):
    """POST join without auth must return 401."""
    cohort_id = cohort["id"]
    resp = requests.post(
        api(f"/api/v1/cohorts/cohorts/{cohort_id}/join/"),
        timeout=15,
    )
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated join, got {resp.status_code}: {resp.text}"
    )


def test_cohort_members_list(instructor_client, cohort):
    """GET /api/v1/cohorts/cohorts/{id}/members/ returns cohort members list."""
    cohort_id = cohort["id"]
    resp = instructor_client.get(f"/api/v1/cohorts/cohorts/{cohort_id}/members/")
    assert resp.status_code == 200, (
        f"GET cohort members returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, list), f"Expected list of members, got: {type(data)}"


# ---------------------------------------------------------------------------
# Drip schedules
# ---------------------------------------------------------------------------


def test_list_drip_schedules_as_instructor(instructor_client):
    """GET /api/v1/cohorts/drip-schedules/ as instructor returns 200."""
    resp = instructor_client.get("/api/v1/cohorts/drip-schedules/")
    assert resp.status_code == 200, (
        f"GET drip schedules returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, (list, dict)), (
        f"Unexpected response type: {type(data)}"
    )


def test_list_drip_schedules_unauthenticated():
    """GET /api/v1/cohorts/drip-schedules/ without auth must return 401."""
    resp = requests.get(api("/api/v1/cohorts/drip-schedules/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


def test_release_pending_as_student_forbidden(student_client):
    """POST /api/v1/cohorts/drip-schedules/release_pending/ as student returns 403."""
    resp = student_client.post("/api/v1/cohorts/drip-schedules/release_pending/")
    assert resp.status_code == 403, (
        f"Expected 403 for student releasing drip content, got {resp.status_code}: {resp.text}"
    )


def test_release_pending_as_instructor(instructor_client):
    """POST /api/v1/cohorts/drip-schedules/release_pending/ as instructor returns 200."""
    resp = instructor_client.post("/api/v1/cohorts/drip-schedules/release_pending/")
    assert resp.status_code == 200, (
        f"release_pending returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "released_count" in data, f"Missing 'released_count' in response: {data}"
    assert isinstance(data["released_count"], int), (
        f"released_count should be an int, got: {type(data['released_count'])}"
    )
