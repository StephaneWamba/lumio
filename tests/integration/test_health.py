"""
Integration tests: health check and API schema endpoints.

These are the first tests that should pass — they verify the server is up
and the OpenAPI spec is being served correctly.
"""

import pytest
import requests

from .conftest import api

pytestmark = pytest.mark.integration


def test_health_check():
    """GET /health/ must return 200 with status=healthy."""
    resp = requests.get(api("/health/"), timeout=15)
    assert resp.status_code == 200, (
        f"Health check returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "status" in data, f"Missing 'status' key in health response: {data}"
    assert data["status"] == "healthy", (
        f"Expected status='healthy', got: {data['status']}"
    )


def test_api_schema():
    """GET /api/schema/ must return 200 (OpenAPI YAML/JSON)."""
    resp = requests.get(api("/api/schema/"), timeout=15)
    assert resp.status_code == 200, (
        f"API schema endpoint returned {resp.status_code}: {resp.text}"
    )
    # drf-spectacular serves YAML by default; just verify it's non-empty
    assert len(resp.content) > 100, "Schema response body is suspiciously short"


def test_swagger_ui():
    """GET /api/docs/ must return 200 (Swagger UI HTML page)."""
    resp = requests.get(api("/api/docs/"), timeout=15)
    assert resp.status_code == 200, (
        f"Swagger UI endpoint returned {resp.status_code}: {resp.text}"
    )
    # Swagger UI is always HTML
    content_type = resp.headers.get("Content-Type", "")
    assert "text/html" in content_type, (
        f"Expected HTML content type for Swagger UI, got: {content_type}"
    )
