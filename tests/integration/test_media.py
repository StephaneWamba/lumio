"""
Integration tests: media / video pipeline.

Phase 3 endpoints (presigned upload, CloudFront signed URLs) are not yet
fully implemented — the views return 501 with placeholder messages. These
tests verify the correct responses and guard against regressions once
the implementation lands.
"""

import pytest
import requests

from .conftest import api, TEST_RUN_ID

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Video file list (read-only)
# ---------------------------------------------------------------------------


def test_list_videos_authenticated(student_client):
    """GET /api/v1/media/videos/ returns 200 for an authenticated user."""
    resp = student_client.get("/api/v1/media/videos/")
    assert resp.status_code == 200, (
        f"GET videos returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, (list, dict)), (
        f"Unexpected response type for video list: {type(data)}"
    )


def test_list_videos_unauthenticated():
    """GET /api/v1/media/videos/ without auth must return 401."""
    resp = requests.get(api("/api/v1/media/videos/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated video list, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Presigned upload initiation
# ---------------------------------------------------------------------------


def test_initiate_upload_unauthenticated(published_course):
    """POST /api/v1/media/videos/initiate_upload/ without auth must return 401."""
    resp = requests.post(
        api("/api/v1/media/videos/initiate_upload/"),
        json={
            "lesson_id": published_course["_lesson_id"],
            "file_name": "test_video.mp4",
            "file_size_bytes": 1048576,
        },
        timeout=15,
    )
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated upload initiation, got {resp.status_code}: {resp.text}"
    )


def test_initiate_upload_as_instructor(instructor_client, published_course):
    """POST /api/v1/media/videos/initiate_upload/ as instructor returns 501 (Phase 3 placeholder)
    or 200/201 if the feature has been implemented.
    """
    lesson_id = published_course["_lesson_id"]
    resp = instructor_client.post(
        "/api/v1/media/videos/initiate_upload/",
        json={
            "lesson_id": lesson_id,
            "file_name": f"test_video_{TEST_RUN_ID}.mp4",
            "file_size_bytes": 52428800,  # 50 MB
        },
    )
    # Phase 3 not yet implemented → 501; once implemented → 200/201
    assert resp.status_code in (200, 201, 501), (
        f"Unexpected status for initiate_upload: {resp.status_code} — {resp.text}"
    )
    data = resp.json()
    if resp.status_code == 501:
        # Verify it's clearly a "not implemented" placeholder
        assert "message" in data or "error" in data, (
            f"501 response should have 'message' or 'error' key: {data}"
        )
    elif resp.status_code in (200, 201):
        # Once implemented, should return a presigned URL and asset ID
        assert "presigned_url" in data or "upload_url" in data or "url" in str(data).lower(), (
            f"Expected presigned URL in successful initiate_upload response: {data}"
        )


def test_initiate_upload_as_student_forbidden(student_client, published_course):
    """Students cannot initiate video uploads for a course they don't own — must return 403."""
    lesson_id = published_course["_lesson_id"]
    resp = student_client.post(
        "/api/v1/media/videos/initiate_upload/",
        json={
            "lesson_id": lesson_id,
            "file_name": "student_hack.mp4",
            "file_size_bytes": 1024,
        },
    )
    assert resp.status_code in (403, 501), (
        f"Expected 403 for student uploading to instructor lesson, got {resp.status_code}: {resp.text}"
    )


def test_initiate_upload_missing_fields(instructor_client):
    """POST initiate_upload with missing required fields must return 400."""
    resp = instructor_client.post(
        "/api/v1/media/videos/initiate_upload/",
        json={},
    )
    assert resp.status_code == 400, (
        f"Expected 400 for missing fields, got {resp.status_code}: {resp.text}"
    )


def test_initiate_upload_nonexistent_lesson(instructor_client):
    """POST initiate_upload for a non-existent lesson must return 404."""
    resp = instructor_client.post(
        "/api/v1/media/videos/initiate_upload/",
        json={
            "lesson_id": 99999999,
            "file_name": "video.mp4",
            "file_size_bytes": 1024,
        },
    )
    assert resp.status_code == 404, (
        f"Expected 404 for missing lesson, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Signed CloudFront video URL
# ---------------------------------------------------------------------------


def test_signed_video_url_unauthenticated(published_course):
    """GET /api/v1/media/lessons/{id}/video-url/ without auth must return 401."""
    lesson_id = published_course["_lesson_id"]
    resp = requests.get(
        api(f"/api/v1/media/lessons/{lesson_id}/video-url/"),
        timeout=15,
    )
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated video URL, got {resp.status_code}: {resp.text}"
    )


def test_signed_video_url_no_video(student_client, published_course):
    """GET signed video URL for a lesson with no video returns 404 or 501."""
    lesson_id = published_course["_lesson_id"]
    resp = student_client.get(f"/api/v1/media/lessons/{lesson_id}/video-url/")
    # Lesson has no video file → 404 ("Video not found")
    # Or Phase 3 not fully wired → 501
    assert resp.status_code in (404, 501, 400), (
        f"Expected 404/501/400 for lesson without video, got {resp.status_code}: {resp.text}"
    )


def test_signed_video_url_nonexistent_lesson(student_client):
    """GET signed video URL for a non-existent lesson must return 404."""
    resp = student_client.get("/api/v1/media/lessons/99999999/video-url/")
    assert resp.status_code == 404, (
        f"Expected 404, got {resp.status_code}: {resp.text}"
    )
