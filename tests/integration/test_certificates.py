"""
Integration tests: certificates API.

Covers listing earned certificates, certificate templates, award criteria,
and the public verification endpoint.
"""

import pytest
import requests
from uuid import uuid4

from .conftest import api, TEST_RUN_ID

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Earned certificates
# ---------------------------------------------------------------------------


def test_list_earned_certificates_as_student(student_client):
    """GET /api/v1/certificates/earned/ as student returns 200 (own certs, may be empty)."""
    resp = student_client.get("/api/v1/certificates/earned/")
    assert resp.status_code == 200, (
        f"GET earned certificates returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    # New student has no certificates yet — expect empty list
    assert isinstance(items, list), f"Expected list of certificates: {type(items)}"


def test_list_earned_certificates_as_instructor(instructor_client):
    """GET /api/v1/certificates/earned/ as instructor returns 200 (certs for their courses)."""
    resp = instructor_client.get("/api/v1/certificates/earned/")
    assert resp.status_code == 200, (
        f"GET earned certificates for instructor returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert isinstance(items, list), f"Expected list of certificates: {type(items)}"


def test_list_earned_certificates_unauthenticated():
    """GET /api/v1/certificates/earned/ without auth must return 401."""
    resp = requests.get(api("/api/v1/certificates/earned/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


def test_get_earned_certificate_not_found(student_client):
    """GET /api/v1/certificates/earned/99999999/ returns 404 for non-existent certificate."""
    resp = student_client.get("/api/v1/certificates/earned/99999999/")
    assert resp.status_code == 404, (
        f"Expected 404 for non-existent certificate, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Certificate templates
# ---------------------------------------------------------------------------


def test_list_certificate_templates_as_instructor(instructor_client):
    """GET /api/v1/certificates/templates/ as instructor returns 200."""
    resp = instructor_client.get("/api/v1/certificates/templates/")
    assert resp.status_code == 200, (
        f"GET certificate templates returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, (list, dict)), (
        f"Unexpected type for templates list: {type(data)}"
    )


def test_list_certificate_templates_as_student(student_client):
    """GET /api/v1/certificates/templates/ as student returns 200 (sees enrolled-course templates)."""
    resp = student_client.get("/api/v1/certificates/templates/")
    assert resp.status_code == 200, (
        f"GET certificate templates for student returned {resp.status_code}: {resp.text}"
    )


def test_list_certificate_templates_unauthenticated():
    """GET /api/v1/certificates/templates/ without auth must return 401."""
    resp = requests.get(api("/api/v1/certificates/templates/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


def test_create_certificate_template_as_instructor(instructor_client, published_course):
    """POST /api/v1/certificates/templates/ as instructor creates a template."""
    course_id = published_course["id"]
    resp = instructor_client.post(
        "/api/v1/certificates/templates/",
        json={
            "course_id": course_id,
            "name": f"Test Certificate Template {TEST_RUN_ID}",
            "content": "Congratulations {student_name} on completing {course_title}!",
            "is_active": True,
        },
    )
    # 201 created, or 400 if template already exists for this course
    assert resp.status_code in (201, 400), (
        f"Unexpected status from template creation: {resp.status_code} — {resp.text}"
    )
    if resp.status_code == 201:
        data = resp.json()
        assert "id" in data, f"Missing 'id' in template response: {data}"


def test_create_certificate_template_as_student_forbidden(student_client, published_course):
    """Students cannot create certificate templates — must return 403."""
    resp = student_client.post(
        "/api/v1/certificates/templates/",
        json={
            "course_id": published_course["id"],
            "name": "Forbidden Template",
            "content": "Nope.",
        },
    )
    assert resp.status_code == 403, (
        f"Expected 403 for student creating template, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Certificate awards
# ---------------------------------------------------------------------------


def test_list_certificate_awards_as_instructor(instructor_client):
    """GET /api/v1/certificates/awards/ as instructor returns 200."""
    resp = instructor_client.get("/api/v1/certificates/awards/")
    assert resp.status_code == 200, (
        f"GET certificate awards returned {resp.status_code}: {resp.text}"
    )


def test_list_certificate_awards_as_student_empty(student_client):
    """GET /api/v1/certificates/awards/ as student returns 200 with empty list (IsInstructor → .none())."""
    resp = student_client.get("/api/v1/certificates/awards/")
    # IsInstructor permission class should deny non-instructors
    assert resp.status_code in (200, 403), (
        f"Unexpected status for student accessing awards: {resp.status_code} — {resp.text}"
    )
    if resp.status_code == 200:
        data = resp.json()
        items = data if isinstance(data, list) else data.get("results", [])
        assert items == [], f"Expected empty awards list for student, got: {items}"


# ---------------------------------------------------------------------------
# Verification endpoint (public)
# ---------------------------------------------------------------------------


def test_verify_certificate_invalid_slug(student_client):
    """GET /api/v1/certificates/earned/{invalid-slug}/ returns 404 for unknown slug.

    The EarnedCertificateViewSet uses integer PKs by default (ReadOnlyModelViewSet).
    Using a clearly non-existent PK returns 404.
    """
    resp = student_client.get("/api/v1/certificates/earned/00000000-nonexistent-slug-here/")
    assert resp.status_code == 404, (
        f"Expected 404 for invalid certificate slug, got {resp.status_code}: {resp.text}"
    )


def test_verify_certificate_nonexistent_pk(student_client):
    """GET /api/v1/certificates/earned/99999999/ returns 404."""
    resp = student_client.get("/api/v1/certificates/earned/99999999/")
    assert resp.status_code == 404, (
        f"Expected 404 for non-existent certificate PK, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Issue certificate (instructor action)
# ---------------------------------------------------------------------------


def test_issue_certificate_requires_enrollment_id(instructor_client):
    """POST /api/v1/certificates/earned/issue_for_enrollment/ without enrollment_id → 400."""
    resp = instructor_client.post(
        "/api/v1/certificates/earned/issue_for_enrollment/",
        json={},
    )
    assert resp.status_code == 400, (
        f"Expected 400 for missing enrollment_id, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "enrollment_id" in str(data).lower() or "detail" in data, (
        f"Expected informative error: {data}"
    )


def test_issue_certificate_nonexistent_enrollment(instructor_client):
    """POST /api/v1/certificates/earned/issue_for_enrollment/ for missing enrollment → 404."""
    resp = instructor_client.post(
        "/api/v1/certificates/earned/issue_for_enrollment/",
        json={"enrollment_id": 99999999},
    )
    assert resp.status_code == 404, (
        f"Expected 404 for non-existent enrollment, got {resp.status_code}: {resp.text}"
    )
