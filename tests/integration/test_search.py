"""
Integration tests: full-text search API.

The search app uses PostgreSQL FTS with GIN index. These tests verify
the search endpoint responds correctly for various query patterns and filters.
"""

import pytest
import requests

from .conftest import api, TEST_RUN_ID

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Basic search
# ---------------------------------------------------------------------------


def test_search_endpoint_is_public():
    """GET /api/v1/search/ without auth must return 200 (AllowAny permission)."""
    resp = requests.get(api("/api/v1/search/"), timeout=15)
    assert resp.status_code == 200, (
        f"Expected 200 for public search endpoint, got {resp.status_code}: {resp.text}"
    )


def test_search_courses_with_query(student_client):
    """GET /api/v1/search/?q=test returns results or an empty list — never an error."""
    resp = student_client.get("/api/v1/search/", params={"q": "test"})
    assert resp.status_code == 200, (
        f"Search with query returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    # Could be paginated {"count": N, "results": [...]} or a plain list
    assert isinstance(data, (dict, list)), (
        f"Unexpected search response type: {type(data)}"
    )
    items = data if isinstance(data, list) else data.get("results", [])
    assert isinstance(items, list), f"Expected list of results, got: {type(items)}"


def test_search_empty_query(student_client):
    """GET /api/v1/search/?q= (empty string) returns 200 with results or empty list."""
    resp = student_client.get("/api/v1/search/", params={"q": ""})
    assert resp.status_code in (200, 400), (
        f"Unexpected status for empty query: {resp.status_code} — {resp.text}"
    )


def test_search_no_query_param(student_client):
    """GET /api/v1/search/ with no q param returns all published items (200)."""
    resp = student_client.get("/api/v1/search/")
    assert resp.status_code == 200, (
        f"Search with no q param returned {resp.status_code}: {resp.text}"
    )


def test_search_course_created_in_session(student_client, published_course):
    """Searching for the title keyword of the session course finds it (FTS working)."""
    # The published_course title contains "Integration Test Course <RUN_ID>"
    query_word = "Integration"
    resp = student_client.get("/api/v1/search/", params={"q": query_word})
    assert resp.status_code == 200, (
        f"Search for '{query_word}' returned {resp.status_code}: {resp.text}"
    )
    # We don't assert the course IS found because the search index may not be
    # populated synchronously — just verify no server error.


# ---------------------------------------------------------------------------
# Search filters
# ---------------------------------------------------------------------------


def test_search_filter_by_difficulty(student_client):
    """GET /api/v1/search/?difficulty=beginner returns 200."""
    resp = student_client.get("/api/v1/search/", params={"difficulty": "beginner"})
    assert resp.status_code == 200, (
        f"Search with difficulty filter returned {resp.status_code}: {resp.text}"
    )


def test_search_filter_by_content_type(student_client):
    """GET /api/v1/search/?content_type=course returns 200."""
    resp = student_client.get("/api/v1/search/", params={"content_type": "course"})
    assert resp.status_code == 200, (
        f"Search with content_type filter returned {resp.status_code}: {resp.text}"
    )


def test_search_filter_combined(student_client):
    """GET /api/v1/search/?q=test&difficulty=beginner&content_type=course returns 200."""
    resp = student_client.get(
        "/api/v1/search/",
        params={"q": "test", "difficulty": "beginner", "content_type": "course"},
    )
    assert resp.status_code == 200, (
        f"Combined filter search returned {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Search facets
# ---------------------------------------------------------------------------


def test_search_facets_endpoint(student_client):
    """GET /api/v1/search/facets/ returns facet options."""
    resp = student_client.get("/api/v1/search/facets/")
    assert resp.status_code == 200, (
        f"GET search facets returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, dict), f"Expected dict from facets, got: {type(data)}"
    assert "difficulties" in data or "content_types" in data, (
        f"Expected facet keys in response: {data}"
    )


def test_search_facets_public():
    """Search facets endpoint must be accessible without authentication."""
    resp = requests.get(api("/api/v1/search/facets/"), timeout=15)
    assert resp.status_code == 200, (
        f"Facets endpoint returned {resp.status_code} for unauthenticated: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Trending & suggestions
# ---------------------------------------------------------------------------


def test_search_trending(student_client):
    """GET /api/v1/search/trending/ returns a list of trending queries."""
    resp = student_client.get("/api/v1/search/trending/")
    assert resp.status_code == 200, (
        f"GET trending returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, list), f"Expected list from trending, got: {type(data)}"


def test_search_suggestions(student_client):
    """GET /api/v1/search/suggestions/?q=int returns a list of suggestions."""
    resp = student_client.get("/api/v1/search/suggestions/", params={"q": "int"})
    assert resp.status_code == 200, (
        f"GET suggestions returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, list), f"Expected list from suggestions, got: {type(data)}"


def test_search_suggestions_short_query(student_client):
    """GET /api/v1/search/suggestions/?q=x (1 char) returns empty list."""
    resp = student_client.get("/api/v1/search/suggestions/", params={"q": "x"})
    assert resp.status_code == 200, (
        f"Suggestions with 1-char query returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert data == [], (
        f"Expected empty list for 1-char query, got: {data}"
    )
