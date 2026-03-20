"""
Integration test configuration for Lumio LMS live API.

All tests hit the real production ALB. No mocks. No stubs.
Run with:
    pytest tests/integration/ -v -m integration --no-cov
"""

import pytest
import requests
from uuid import uuid4

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URL = "http://lumio-production-alb-1639211656.eu-central-1.elb.amazonaws.com"

# Unique suffix per test run so created data never collides with a previous run.
TEST_RUN_ID: str = uuid4().hex[:8]


def api(path: str) -> str:
    """Return the full URL for a given API path.

    Examples:
        api("/health/")           → BASE_URL + "/health/"
        api("/api/v1/auth/login/") → BASE_URL + "/api/v1/auth/login/"
    """
    if not path.startswith("/"):
        path = "/" + path
    return BASE_URL + path


# ---------------------------------------------------------------------------
# Low-level helpers (not fixtures — called from fixtures or test code directly)
# ---------------------------------------------------------------------------


def register_user(email: str, password: str, role: str = "student") -> dict:
    """POST to register endpoint and return the response JSON user dict.

    Raises AssertionError if the server does not return 201.
    """
    resp = requests.post(
        api("/api/v1/auth/register/"),
        json={
            "email": email,
            "password": password,
            "password2": password,
            "name": f"Test {role.capitalize()} {TEST_RUN_ID}",
            "role": role,
        },
        timeout=30,
    )
    assert resp.status_code == 201, (
        f"register_user failed for {email} (role={role}): "
        f"status={resp.status_code} body={resp.text}"
    )
    data = resp.json()
    # The register endpoint returns {"message": "...", "user": {...}}
    return data.get("user", data)


def login(email: str, password: str) -> dict:
    """POST to login endpoint once and return {"access": ..., "refresh": ...}.

    Single call — callers must not call this multiple times for the same user
    to avoid exhausting the auth_login rate limit (5/min in production).
    """
    resp = requests.post(
        api("/api/v1/auth/login/"),
        json={"email": email, "password": password},
        timeout=30,
    )
    assert resp.status_code == 200, (
        f"login failed for {email}: status={resp.status_code} body={resp.text}"
    )
    data = resp.json()
    assert "access" in data, f"No 'access' token in login response: {data}"
    return data


def get_token(email: str, password: str) -> str:
    """Return the access token. Thin wrapper around login()."""
    return login(email, password)["access"]


def get_refresh_token(email: str, password: str) -> str:
    """Return the refresh token. Thin wrapper around login()."""
    return login(email, password)["refresh"]


# ---------------------------------------------------------------------------
# AuthedClient — a thin requests.Session wrapper that injects the Bearer token
# ---------------------------------------------------------------------------


class AuthedClient:
    """Wraps requests.Session with Authorization: Bearer header pre-set.

    Supports .get(), .post(), .patch(), .put(), .delete() with the same
    signature as requests. The 'timeout' kwarg defaults to 30 s on every call.
    """

    DEFAULT_TIMEOUT = 30

    def __init__(self, token: str):
        self.token = token
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

    def get(self, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        return self._session.get(api(path), **kwargs)

    def post(self, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        return self._session.post(api(path), **kwargs)

    def patch(self, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        return self._session.patch(api(path), **kwargs)

    def put(self, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        return self._session.put(api(path), **kwargs)

    def delete(self, path: str, **kwargs) -> requests.Response:
        kwargs.setdefault("timeout", self.DEFAULT_TIMEOUT)
        return self._session.delete(api(path), **kwargs)


# ---------------------------------------------------------------------------
# Session-scoped fixtures — created once per pytest session to minimise calls
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def student_credentials() -> dict:
    """Return student credentials.

    If LUMIO_TEST_STUDENT_EMAIL / LUMIO_TEST_STUDENT_PASSWORD are set, reuse
    those pre-existing accounts (avoids register throttle in production).
    Otherwise register a fresh account.
    """
    import os
    email = os.environ.get("LUMIO_TEST_STUDENT_EMAIL", f"student_{TEST_RUN_ID}@test.lumio.io")
    password = os.environ.get("LUMIO_TEST_STUDENT_PASSWORD", f"TestPass_{TEST_RUN_ID}_S!")
    if not os.environ.get("LUMIO_TEST_STUDENT_EMAIL"):
        user = register_user(email, password, role="student")
    else:
        user = {}  # will be fetched via student_tokens fixture
    return {"email": email, "password": password, "user": user}


@pytest.fixture(scope="session")
def instructor_credentials() -> dict:
    """Return instructor credentials.

    If LUMIO_TEST_INSTRUCTOR_EMAIL / LUMIO_TEST_INSTRUCTOR_PASSWORD are set,
    reuse those pre-existing accounts. Otherwise register a fresh account.
    """
    import os
    email = os.environ.get("LUMIO_TEST_INSTRUCTOR_EMAIL", f"instructor_{TEST_RUN_ID}@test.lumio.io")
    password = os.environ.get("LUMIO_TEST_INSTRUCTOR_PASSWORD", f"TestPass_{TEST_RUN_ID}_I!")
    if not os.environ.get("LUMIO_TEST_INSTRUCTOR_EMAIL"):
        user = register_user(email, password, role="instructor")
    else:
        user = {}  # will be fetched via instructor_tokens fixture
    return {"email": email, "password": password, "user": user}


@pytest.fixture(scope="session")
def student_tokens(student_credentials) -> dict:
    """Login once and return both access + refresh tokens for the session student."""
    tokens = login(student_credentials["email"], student_credentials["password"])
    return tokens


@pytest.fixture(scope="session")
def instructor_tokens(instructor_credentials) -> dict:
    """Login once and return both access + refresh tokens for the session instructor."""
    tokens = login(instructor_credentials["email"], instructor_credentials["password"])
    return tokens


@pytest.fixture(scope="session")
def student_client(student_tokens) -> AuthedClient:
    """Return an AuthedClient authenticated as the session student."""
    return AuthedClient(student_tokens["access"])


@pytest.fixture(scope="session")
def instructor_client(instructor_tokens) -> AuthedClient:
    """Return an AuthedClient authenticated as the session instructor."""
    return AuthedClient(instructor_tokens["access"])


@pytest.fixture(scope="session")
def student_refresh_token(student_tokens) -> str:
    """Return the refresh token for the session student."""
    return student_tokens["refresh"]


@pytest.fixture(scope="session")
def instructor_refresh_token(instructor_tokens) -> str:
    """Return the refresh token for the session instructor."""
    return instructor_tokens["refresh"]


@pytest.fixture(scope="session")
def published_course(instructor_client) -> dict:
    """Create a full course (course + section + lesson) as the instructor, publish it.

    Returns the course dict from the API. Scoped to session so all tests share the
    same course without repeated round-trips.
    """
    # 1. Create course
    resp = instructor_client.post(
        "/api/v1/courses/courses/",
        json={
            "title": f"Integration Test Course {TEST_RUN_ID}",
            "description": "Auto-generated course for integration tests.",
            "short_description": "Integration test course.",
            "difficulty": "beginner",
            "language": "en",
        },
    )
    assert resp.status_code == 201, (
        f"published_course fixture: course creation failed: "
        f"status={resp.status_code} body={resp.text}"
    )
    course = resp.json()
    course_id = course["id"]

    # 2. Create a section inside the course
    resp = instructor_client.post(
        f"/api/v1/courses/courses/{course_id}/sections/",
        json={
            "title": f"Section 1 - {TEST_RUN_ID}",
            "description": "First test section.",
            "order": 1,
        },
    )
    assert resp.status_code == 201, (
        f"published_course fixture: section creation failed: "
        f"status={resp.status_code} body={resp.text}"
    )
    section = resp.json()
    section_id = section["id"]

    # 3. Create a lesson inside the section
    resp = instructor_client.post(
        f"/api/v1/courses/courses/{course_id}/sections/{section_id}/lessons/",
        json={
            "title": f"Lesson 1 - {TEST_RUN_ID}",
            "description": "First test lesson.",
            "lesson_type": "text",
            "content": "This is the lesson content for integration testing.",
            "order": 1,
            "is_free_preview": True,
        },
    )
    assert resp.status_code == 201, (
        f"published_course fixture: lesson creation failed: "
        f"status={resp.status_code} body={resp.text}"
    )
    lesson = resp.json()

    # 4. Publish the course
    resp = instructor_client.get(f"/api/v1/courses/courses/{course_id}/publish/")
    assert resp.status_code == 200, (
        f"published_course fixture: publish failed: "
        f"status={resp.status_code} body={resp.text}"
    )

    # 5. Return enriched dict with nested ids for convenience
    course["_section_id"] = section_id
    course["_lesson_id"] = lesson["id"]
    return course


@pytest.fixture(scope="session")
def student_enrollment(student_client, published_course) -> dict:
    """Enroll the session student in the published course once.

    Returns the enrollment dict. Used by progress/quiz/certificate tests.
    """
    course_id = published_course["id"]
    resp = student_client.post(
        "/api/v1/enrollments/enrollments/enroll/",
        json={"course_id": course_id},
    )
    # 201 = newly enrolled, 400 "Already enrolled" is also acceptable
    if resp.status_code == 400 and "Already enrolled" in resp.text:
        # Fetch existing enrollment
        list_resp = student_client.get("/api/v1/enrollments/enrollments/")
        assert list_resp.status_code == 200, (
            f"student_enrollment fixture: failed to list enrollments: "
            f"status={list_resp.status_code} body={list_resp.text}"
        )
        enrollments = list_resp.json()
        # Handle both paginated and non-paginated responses
        items = enrollments if isinstance(enrollments, list) else enrollments.get("results", [])
        for e in items:
            if e.get("course") == course_id or (
                isinstance(e.get("course"), dict) and e["course"].get("id") == course_id
            ):
                return e
        pytest.skip("Could not retrieve existing enrollment for student")
    assert resp.status_code == 201, (
        f"student_enrollment fixture: enrollment creation failed: "
        f"status={resp.status_code} body={resp.text}"
    )
    return resp.json()
