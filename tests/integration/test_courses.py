"""
Integration tests: course management API.

Covers CRUD for courses, sections, and lessons. Also covers permission
enforcement (student vs. instructor) and the publish/unpublish actions.
"""

import pytest
import requests
from uuid import uuid4

from .conftest import api, TEST_RUN_ID

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Course listing
# ---------------------------------------------------------------------------


def test_list_courses_unauthenticated():
    """GET /api/v1/courses/courses/ without a token.

    The CourseViewSet uses AllowAny permission. Unauthenticated users see
    published courses only. This test verifies the endpoint responds with 200.
    """
    resp = requests.get(api("/api/v1/courses/courses/"), timeout=15)
    # AllowAny — so should be 200 (may return empty list for new environment)
    assert resp.status_code == 200, (
        f"Expected 200 for unauthenticated course list, got {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    # Could be paginated {"count": N, "results": [...]} or plain list
    assert isinstance(data, (dict, list)), (
        f"Unexpected response type for course list: {type(data)}"
    )


def test_list_courses_authenticated(student_client):
    """GET /api/v1/courses/courses/ authenticated returns 200 with a results structure."""
    resp = student_client.get("/api/v1/courses/courses/")
    assert resp.status_code == 200, (
        f"Authenticated course list returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    # Paginated response
    if isinstance(data, dict):
        assert "results" in data or "count" in data, (
            f"Unexpected paginated response shape: {data}"
        )
    else:
        assert isinstance(data, list), f"Expected list or paginated dict, got: {type(data)}"


def test_list_courses_instructor_sees_own(instructor_client, published_course):
    """Instructors should see their own courses (published or not)."""
    resp = instructor_client.get("/api/v1/courses/courses/")
    assert resp.status_code == 200, (
        f"Instructor course list returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    course_ids = [c["id"] for c in items]
    assert published_course["id"] in course_ids, (
        f"Instructor's published_course {published_course['id']} not found in list. "
        f"IDs returned: {course_ids}"
    )


# ---------------------------------------------------------------------------
# Course creation
# ---------------------------------------------------------------------------


def test_create_course_as_instructor(instructor_client):
    """POST /api/v1/courses/courses/ as instructor returns 201 with course data."""
    unique = uuid4().hex[:6]
    resp = instructor_client.post(
        "/api/v1/courses/courses/",
        json={
            "title": f"Test Course {unique}",
            "description": "A course created by the integration test suite.",
            "short_description": "Integration test.",
            "difficulty": "intermediate",
            "language": "en",
        },
    )
    assert resp.status_code == 201, (
        f"Course creation failed: status={resp.status_code} body={resp.text}"
    )
    data = resp.json()
    assert "id" in data, f"Missing 'id' in course creation response: {data}"
    assert data.get("title", "").startswith("Test Course"), (
        f"Unexpected title in response: {data.get('title')}"
    )


def test_create_course_as_student_forbidden(student_client):
    """Students cannot create courses — must return 403."""
    resp = student_client.post(
        "/api/v1/courses/courses/",
        json={
            "title": "Forbidden Course",
            "description": "Students cannot do this.",
            "difficulty": "beginner",
        },
    )
    assert resp.status_code == 403, (
        f"Expected 403 for student creating course, got {resp.status_code}: {resp.text}"
    )


def test_create_course_unauthenticated():
    """Unauthenticated POST must return 403 (AllowAny + perform_create check)."""
    resp = requests.post(
        api("/api/v1/courses/courses/"),
        json={
            "title": "Anon Course",
            "description": "Should fail.",
            "difficulty": "beginner",
        },
        timeout=15,
    )
    assert resp.status_code in (401, 403), (
        f"Expected 401/403 for unauthenticated course creation, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Course detail & update
# ---------------------------------------------------------------------------


def test_get_course_detail(student_client, published_course):
    """GET /api/v1/courses/courses/{id}/ returns full course data."""
    course_id = published_course["id"]
    resp = student_client.get(f"/api/v1/courses/courses/{course_id}/")
    assert resp.status_code == 200, (
        f"GET course detail returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data["id"] == course_id, (
        f"Expected course id={course_id}, got: {data.get('id')}"
    )
    assert "title" in data, f"Missing 'title' in course detail: {data}"
    assert "description" in data, f"Missing 'description' in course detail: {data}"


def test_get_course_detail_not_found(student_client):
    """GET a non-existent course id returns 404."""
    resp = student_client.get("/api/v1/courses/courses/99999999/")
    assert resp.status_code == 404, (
        f"Expected 404 for missing course, got {resp.status_code}: {resp.text}"
    )


def test_update_course_as_instructor(instructor_client, published_course):
    """PATCH /api/v1/courses/courses/{id}/ by the owner instructor updates the title."""
    course_id = published_course["id"]
    new_title = f"Updated Title {TEST_RUN_ID}"
    resp = instructor_client.patch(
        f"/api/v1/courses/courses/{course_id}/",
        json={"title": new_title},
    )
    assert resp.status_code == 200, (
        f"PATCH course returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data.get("title") == new_title, (
        f"Expected updated title='{new_title}', got: {data.get('title')}"
    )


def test_update_course_as_student_forbidden(student_client, published_course):
    """Students cannot update a course — must return 403."""
    course_id = published_course["id"]
    resp = student_client.patch(
        f"/api/v1/courses/courses/{course_id}/",
        json={"title": "Hijacked Title"},
    )
    assert resp.status_code == 403, (
        f"Expected 403 for student patching course, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def test_create_section(instructor_client, published_course):
    """POST /api/v1/courses/courses/{id}/sections/ creates a section."""
    course_id = published_course["id"]
    resp = instructor_client.post(
        f"/api/v1/courses/courses/{course_id}/sections/",
        json={
            "title": f"Extra Section {TEST_RUN_ID}",
            "description": "A second section for testing.",
            "order": 2,
        },
    )
    assert resp.status_code == 201, (
        f"Section creation failed: status={resp.status_code} body={resp.text}"
    )
    data = resp.json()
    assert "id" in data, f"Missing 'id' in section creation response: {data}"
    assert "title" in data, f"Missing 'title' in section creation response: {data}"


def test_list_sections(student_client, published_course):
    """GET /api/v1/courses/courses/{id}/sections/ returns a list."""
    course_id = published_course["id"]
    resp = student_client.get(f"/api/v1/courses/courses/{course_id}/sections/")
    assert resp.status_code == 200, (
        f"GET sections returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert len(items) >= 1, (
        f"Expected at least 1 section for course {course_id}, got: {items}"
    )


def test_create_section_as_student_forbidden(student_client, published_course):
    """Students cannot create sections — must return 403."""
    course_id = published_course["id"]
    resp = student_client.post(
        f"/api/v1/courses/courses/{course_id}/sections/",
        json={"title": "Forbidden Section", "order": 99},
    )
    assert resp.status_code == 403, (
        f"Expected 403 for student creating section, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Lessons
# ---------------------------------------------------------------------------


def test_create_lesson(instructor_client, published_course):
    """POST /api/v1/courses/courses/{cid}/sections/{sid}/lessons/ creates a lesson."""
    course_id = published_course["id"]
    section_id = published_course["_section_id"]
    resp = instructor_client.post(
        f"/api/v1/courses/courses/{course_id}/sections/{section_id}/lessons/",
        json={
            "title": f"Extra Lesson {TEST_RUN_ID}",
            "description": "Auto-created lesson.",
            "lesson_type": "text",
            "content": "Lesson body text.",
            "order": 2,
        },
    )
    assert resp.status_code == 201, (
        f"Lesson creation failed: status={resp.status_code} body={resp.text}"
    )
    data = resp.json()
    assert "id" in data, f"Missing 'id' in lesson creation response: {data}"


def test_list_lessons(student_client, published_course):
    """GET /api/v1/courses/courses/{cid}/sections/{sid}/lessons/ returns a list."""
    course_id = published_course["id"]
    section_id = published_course["_section_id"]
    resp = student_client.get(
        f"/api/v1/courses/courses/{course_id}/sections/{section_id}/lessons/"
    )
    assert resp.status_code == 200, (
        f"GET lessons returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert len(items) >= 1, (
        f"Expected at least 1 lesson for section {section_id}, got: {items}"
    )


def test_get_lesson_detail(student_client, published_course):
    """GET /api/v1/courses/courses/{cid}/sections/{sid}/lessons/{lid}/ returns lesson data."""
    course_id = published_course["id"]
    section_id = published_course["_section_id"]
    lesson_id = published_course["_lesson_id"]
    resp = student_client.get(
        f"/api/v1/courses/courses/{course_id}/sections/{section_id}/lessons/{lesson_id}/"
    )
    assert resp.status_code == 200, (
        f"GET lesson detail returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data["id"] == lesson_id, (
        f"Expected lesson id={lesson_id}, got: {data.get('id')}"
    )


# ---------------------------------------------------------------------------
# Publish / unpublish
# ---------------------------------------------------------------------------


def test_publish_course(instructor_client):
    """GET /api/v1/courses/courses/{id}/publish/ by instructor returns 200."""
    # Create a fresh unpublished course to publish in this test
    unique = uuid4().hex[:6]
    create_resp = instructor_client.post(
        "/api/v1/courses/courses/",
        json={
            "title": f"Publish Test Course {unique}",
            "description": "Will be published.",
            "difficulty": "beginner",
        },
    )
    assert create_resp.status_code == 201, (
        f"Could not create course for publish test: {create_resp.text}"
    )
    course_id = create_resp.json()["id"]

    resp = instructor_client.get(f"/api/v1/courses/courses/{course_id}/publish/")
    assert resp.status_code == 200, (
        f"Publish action returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "message" in data or "published" in str(data).lower(), (
        f"Unexpected publish response: {data}"
    )


def test_unpublish_course(instructor_client):
    """GET /api/v1/courses/courses/{id}/unpublish/ by instructor returns 200."""
    # Create and publish a course, then unpublish it
    unique = uuid4().hex[:6]
    create_resp = instructor_client.post(
        "/api/v1/courses/courses/",
        json={
            "title": f"Unpublish Test Course {unique}",
            "description": "Will be published then unpublished.",
            "difficulty": "beginner",
        },
    )
    assert create_resp.status_code == 201, (
        f"Could not create course for unpublish test: {create_resp.text}"
    )
    course_id = create_resp.json()["id"]

    # Publish first
    pub_resp = instructor_client.get(f"/api/v1/courses/courses/{course_id}/publish/")
    assert pub_resp.status_code == 200, (
        f"Could not publish course before unpublish test: {pub_resp.text}"
    )

    # Now unpublish
    unpub_resp = instructor_client.get(f"/api/v1/courses/courses/{course_id}/unpublish/")
    assert unpub_resp.status_code == 200, (
        f"Unpublish action returned {unpub_resp.status_code}: {unpub_resp.text}"
    )
    data = unpub_resp.json()
    assert "message" in data or "unpublish" in str(data).lower(), (
        f"Unexpected unpublish response: {data}"
    )
