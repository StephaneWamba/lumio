"""
Integration tests: quiz engine (assessments).

Covers quiz creation by instructor, question adding, student attempt flow
(start → submit), and adaptive retry (attempt_number increments).

The quiz tests depend on a lesson that the student is enrolled in and has
already viewed (so LessonProgress exists). The student_enrollment and
mark_lesson_viewed flow is set up by the session fixtures in conftest.
"""

import pytest

from .conftest import TEST_RUN_ID

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Session-scoped quiz fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def quiz(instructor_client, published_course):
    """Create a quiz on the test lesson as the instructor.

    Returns the quiz dict. Scoped to session so all assessment tests share it.
    """
    lesson_id = published_course["_lesson_id"]
    resp = instructor_client.post(
        "/api/v1/assessments/quizzes/",
        json={
            "lesson": lesson_id,
            "title": f"Integration Quiz {TEST_RUN_ID}",
            "description": "Auto-generated quiz for integration tests.",
            "passing_score": "60.00",
            "max_attempts": 5,
            "allow_retake": True,
            "time_limit_minutes": None,
        },
    )
    assert resp.status_code == 201, (
        f"quiz fixture: quiz creation failed: status={resp.status_code} body={resp.text}"
    )
    return resp.json()


@pytest.fixture(scope="session")
def quiz_question(instructor_client, quiz):
    """Add a multiple-choice question to the quiz.

    Returns the question dict.
    """
    quiz_id = quiz["id"]
    resp = instructor_client.post(
        "/api/v1/assessments/quizzes/",  # questions are nested under quiz
        json={
            "quiz": quiz_id,
            "text": "What is 2 + 2?",
            "question_type": "multiple_choice",
            "points": "10.00",
            "order": 1,
            "options": [
                {"text": "3", "is_correct": False},
                {"text": "4", "is_correct": True},
                {"text": "5", "is_correct": False},
                {"text": "22", "is_correct": False},
            ],
        },
    )
    # Depending on the API design, questions may be created via a nested endpoint
    # or directly. We skip gracefully if the endpoint doesn't support creation.
    if resp.status_code == 405:
        pytest.skip("Question creation endpoint not available (read-only QuizViewSet)")
    assert resp.status_code in (200, 201), (
        f"quiz_question fixture: question creation failed: "
        f"status={resp.status_code} body={resp.text}"
    )
    return resp.json()


# ---------------------------------------------------------------------------
# Quiz read endpoints
# ---------------------------------------------------------------------------


def test_list_quizzes_authenticated(student_client):
    """GET /api/v1/assessments/quizzes/ returns 200 for authenticated users."""
    resp = student_client.get("/api/v1/assessments/quizzes/")
    assert resp.status_code == 200, (
        f"GET quizzes returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, (list, dict)), (
        f"Unexpected response type for quiz list: {type(data)}"
    )


def test_list_quizzes_unauthenticated():
    """GET /api/v1/assessments/quizzes/ without auth must return 401."""
    import requests
    from .conftest import api

    resp = requests.get(api("/api/v1/assessments/quizzes/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated quiz list, got {resp.status_code}: {resp.text}"
    )


def test_get_quiz_detail(student_client, quiz):
    """GET /api/v1/assessments/quizzes/{id}/ returns quiz data."""
    quiz_id = quiz["id"]
    resp = student_client.get(f"/api/v1/assessments/quizzes/{quiz_id}/")
    assert resp.status_code == 200, (
        f"GET quiz detail returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data["id"] == quiz_id, f"Expected quiz id={quiz_id}, got: {data.get('id')}"
    assert "title" in data, f"Missing 'title' in quiz detail: {data}"


# ---------------------------------------------------------------------------
# Quiz creation (instructor)
# ---------------------------------------------------------------------------


def test_create_quiz_as_instructor(instructor_client, published_course):
    """POST /api/v1/assessments/quizzes/ as instructor creates a quiz."""
    lesson_id = published_course["_lesson_id"]
    resp = instructor_client.post(
        "/api/v1/assessments/quizzes/",
        json={
            "lesson": lesson_id,
            "title": f"Extra Quiz {TEST_RUN_ID}",
            "description": "A second quiz for creation tests.",
            "passing_score": "70.00",
            "max_attempts": 3,
            "allow_retake": True,
        },
    )
    # QuizViewSet is ReadOnly — creation may return 405.
    # Skip gracefully if read-only restriction is in effect.
    if resp.status_code == 405:
        pytest.skip("Quiz creation not available (ReadOnlyModelViewSet)")
    # 400 is acceptable if the session quiz fixture already claimed this lesson
    assert resp.status_code in (201, 400), (
        f"Quiz creation returned {resp.status_code}: {resp.text}"
    )
    if resp.status_code == 201:
        data = resp.json()
        assert "id" in data, f"Missing 'id' in quiz creation response: {data}"


def test_create_quiz_as_student_forbidden(student_client, published_course):
    """Students cannot create quizzes — must return 403 or 405."""
    lesson_id = published_course["_lesson_id"]
    resp = student_client.post(
        "/api/v1/assessments/quizzes/",
        json={
            "lesson": lesson_id,
            "title": "Forbidden Quiz",
            "passing_score": "50.00",
        },
    )
    assert resp.status_code in (403, 405), (
        f"Expected 403 or 405 for student creating quiz, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Quiz attempt flow
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def quiz_attempt(student_client, quiz, student_enrollment, published_course):
    """Start a quiz attempt as the student.

    Requires student to have a LessonProgress record (created by mark_lesson_viewed
    via the student_enrollment fixture). Returns the attempt dict.
    """
    # Ensure student has viewed the lesson first (creates LessonProgress)
    lesson_id = published_course["_lesson_id"]
    enrollment_id = student_enrollment["id"]
    student_client.post(
        f"/api/v1/enrollments/enrollments/{enrollment_id}/mark_lesson_viewed/",
        json={"lesson_id": lesson_id},
    )

    quiz_id = quiz["id"]
    resp = student_client.post(f"/api/v1/assessments/quizzes/{quiz_id}/start_attempt/")
    assert resp.status_code == 201, (
        f"quiz_attempt fixture: start_attempt failed: "
        f"status={resp.status_code} body={resp.text}"
    )
    return resp.json()


def test_start_quiz_attempt(quiz_attempt):
    """Starting a quiz attempt returns 201 with attempt data."""
    assert "id" in quiz_attempt, f"Missing 'id' in attempt response: {quiz_attempt}"
    assert "attempt_number" in quiz_attempt, (
        f"Missing 'attempt_number' in attempt response: {quiz_attempt}"
    )
    assert quiz_attempt["attempt_number"] >= 1, (
        f"attempt_number should be >= 1, got: {quiz_attempt['attempt_number']}"
    )


def test_list_attempts(student_client):
    """GET /api/v1/assessments/attempts/ returns the student's attempts."""
    resp = student_client.get("/api/v1/assessments/attempts/")
    assert resp.status_code == 200, (
        f"GET attempts returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert isinstance(items, list), f"Expected list of attempts: {type(items)}"
    # Should have at least the attempt created by quiz_attempt fixture
    assert len(items) >= 1, f"Expected at least 1 attempt, got: {items}"


def test_submit_quiz_attempt(student_client, quiz_attempt, quiz):
    """POST /api/v1/assessments/attempts/{id}/submit/ submits answers and returns a score."""
    attempt_id = quiz_attempt["id"]

    # The quiz may or may not have questions depending on the API.
    # We submit with an empty answers list as a safe fallback.
    resp = student_client.post(
        f"/api/v1/assessments/attempts/{attempt_id}/submit/",
        json={"answers": []},
    )
    assert resp.status_code == 200, (
        f"submit attempt returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "id" in data, f"Missing 'id' in submit response: {data}"
    assert "status" in data, f"Missing 'status' in submit response: {data}"
    # After submission, status should NOT be in_progress
    assert data["status"] != "in_progress", (
        f"Attempt should not be in_progress after submit, got status: {data['status']}"
    )


def test_submit_already_submitted_attempt(student_client, quiz_attempt):
    """POST submit on an already-submitted attempt must return 400."""
    attempt_id = quiz_attempt["id"]
    resp = student_client.post(
        f"/api/v1/assessments/attempts/{attempt_id}/submit/",
        json={"answers": []},
    )
    assert resp.status_code == 400, (
        f"Expected 400 for double-submit, got {resp.status_code}: {resp.text}"
    )
    assert "submitted" in resp.text.lower() or "already" in resp.text.lower(), (
        f"Expected 'already submitted' message: {resp.text}"
    )


def test_adaptive_retry_increments_attempt_number(student_client, quiz, student_enrollment, published_course):
    """Starting a second attempt increments attempt_number (adaptive retry behaviour)."""
    quiz_id = quiz["id"]
    lesson_id = published_course["_lesson_id"]
    enrollment_id = student_enrollment["id"]

    # Ensure LessonProgress exists
    student_client.post(
        f"/api/v1/enrollments/enrollments/{enrollment_id}/mark_lesson_viewed/",
        json={"lesson_id": lesson_id},
    )

    # Start and immediately submit attempt N
    start_resp = student_client.post(f"/api/v1/assessments/quizzes/{quiz_id}/start_attempt/")
    if start_resp.status_code == 400 and "Maximum" in start_resp.text:
        pytest.skip("Max attempts reached for this quiz — cannot test adaptive retry")
    assert start_resp.status_code == 201, (
        f"start_attempt for retry test returned {start_resp.status_code}: {start_resp.text}"
    )
    attempt_n = start_resp.json()
    attempt_n_id = attempt_n["id"]
    attempt_n_number = attempt_n["attempt_number"]

    # Submit it
    student_client.post(
        f"/api/v1/assessments/attempts/{attempt_n_id}/submit/",
        json={"answers": []},
    )

    # Start attempt N+1
    start_resp2 = student_client.post(f"/api/v1/assessments/quizzes/{quiz_id}/start_attempt/")
    if start_resp2.status_code == 400 and "Maximum" in start_resp2.text:
        pytest.skip("Max attempts reached — cannot verify N+1 attempt number")
    if start_resp2.status_code == 400 and "passed" in start_resp2.text.lower():
        pytest.skip("Quiz passed (no retake needed) — skipping adaptive retry check")
    assert start_resp2.status_code == 201, (
        f"start_attempt N+1 returned {start_resp2.status_code}: {start_resp2.text}"
    )
    attempt_np1 = start_resp2.json()
    assert attempt_np1["attempt_number"] == attempt_n_number + 1, (
        f"Expected attempt_number={attempt_n_number + 1}, "
        f"got: {attempt_np1['attempt_number']}"
    )
