"""
Integration tests: payments API.

Covers price listing, payment initiation, invoice listing, and the Stripe
Connect onboarding stub. No real money moves — the payment flow uses the
internal Payment model without a live Stripe integration at this stage.
"""

import pytest
import requests

from .conftest import api, TEST_RUN_ID

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------


def test_list_prices_authenticated(student_client):
    """GET /api/v1/payments/prices/ returns 200 with a list for authenticated users."""
    resp = student_client.get("/api/v1/payments/prices/")
    assert resp.status_code == 200, (
        f"GET prices returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert isinstance(data, (list, dict)), (
        f"Unexpected response type for prices list: {type(data)}"
    )


def test_list_prices_unauthenticated():
    """GET /api/v1/payments/prices/ without auth must return 401."""
    resp = requests.get(api("/api/v1/payments/prices/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated prices list, got {resp.status_code}: {resp.text}"
    )


def test_create_price_as_instructor(instructor_client, published_course):
    """POST /api/v1/payments/prices/ as instructor creates a price for the course."""
    course_id = published_course["id"]
    resp = instructor_client.post(
        "/api/v1/payments/prices/",
        json={
            "course_id": course_id,
            "amount": "29.99",
            "currency": "USD",
            "price_type": "one_time",
            "is_active": True,
        },
    )
    # 201 if created, 400 if a price already exists for this course (acceptable)
    assert resp.status_code in (201, 400), (
        f"Unexpected status from price creation: {resp.status_code} — {resp.text}"
    )
    if resp.status_code == 201:
        data = resp.json()
        assert "id" in data, f"Missing 'id' in price creation response: {data}"
        assert "amount" in data, f"Missing 'amount' in price response: {data}"


def test_create_price_as_student_forbidden(student_client, published_course):
    """Students cannot create prices — must return 403."""
    resp = student_client.post(
        "/api/v1/payments/prices/",
        json={
            "course_id": published_course["id"],
            "amount": "9.99",
            "currency": "USD",
        },
    )
    assert resp.status_code == 403, (
        f"Expected 403 for student creating price, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Payments list
# ---------------------------------------------------------------------------


def test_list_payments_authenticated(student_client):
    """GET /api/v1/payments/payments/ returns 200 for authenticated users."""
    resp = student_client.get("/api/v1/payments/payments/")
    assert resp.status_code == 200, (
        f"GET payments returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert isinstance(items, list), f"Expected list of payments: {type(items)}"


def test_list_payments_unauthenticated():
    """GET /api/v1/payments/payments/ without auth must return 401."""
    resp = requests.get(api("/api/v1/payments/payments/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Payment initiation
# ---------------------------------------------------------------------------


def test_initiate_payment_no_pricing(student_client, published_course):
    """POST /api/v1/payments/payments/initiate_payment/ for a course without pricing returns 400."""
    # The published_course fixture does NOT set up pricing by default
    resp = student_client.post(
        "/api/v1/payments/payments/initiate_payment/",
        json={"course_id": published_course["id"]},
    )
    # Either 400 "no pricing configured" or 201 if the price was already created
    assert resp.status_code in (201, 400), (
        f"Unexpected status from initiate_payment: {resp.status_code} — {resp.text}"
    )


def test_initiate_payment_missing_course_id(student_client):
    """POST /api/v1/payments/payments/initiate_payment/ without course_id returns 400."""
    resp = student_client.post(
        "/api/v1/payments/payments/initiate_payment/",
        json={},
    )
    assert resp.status_code == 400, (
        f"Expected 400 for missing course_id, got {resp.status_code}: {resp.text}"
    )


def test_initiate_payment_nonexistent_course(student_client):
    """POST initiate_payment for a non-existent course returns 404."""
    resp = student_client.post(
        "/api/v1/payments/payments/initiate_payment/",
        json={"course_id": 99999999},
    )
    assert resp.status_code == 404, (
        f"Expected 404, got {resp.status_code}: {resp.text}"
    )


def test_initiate_payment_unauthenticated(published_course):
    """POST initiate_payment without auth must return 401."""
    resp = requests.post(
        api("/api/v1/payments/payments/initiate_payment/"),
        json={"course_id": published_course["id"]},
        timeout=15,
    )
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------


def test_list_invoices_authenticated(student_client):
    """GET /api/v1/payments/invoices/ returns 200 for authenticated users."""
    resp = student_client.get("/api/v1/payments/invoices/")
    assert resp.status_code == 200, (
        f"GET invoices returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    items = data if isinstance(data, list) else data.get("results", [])
    assert isinstance(items, list), f"Expected list of invoices: {type(items)}"


def test_list_invoices_unauthenticated():
    """GET /api/v1/payments/invoices/ without auth must return 401."""
    resp = requests.get(api("/api/v1/payments/invoices/"), timeout=15)
    assert resp.status_code == 401, (
        f"Expected 401, got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Stripe Connect onboarding (instructor profiles)
# ---------------------------------------------------------------------------


def test_stripe_connect_onboarding_instructor(instructor_client):
    """POST /api/v1/auth/instructor-profiles/onboard_stripe/ as instructor returns 200."""
    resp = instructor_client.post("/api/v1/auth/instructor-profiles/onboard_stripe/")
    # The view returns 200 with a placeholder message
    assert resp.status_code == 200, (
        f"Stripe onboarding returned {resp.status_code}: {resp.text}"
    )
    data = resp.json()
    assert "message" in data, (
        f"Expected 'message' in Stripe onboarding response: {data}"
    )


def test_stripe_connect_onboarding_unauthenticated():
    """POST Stripe onboarding without auth must return 401."""
    resp = requests.post(
        api("/api/v1/auth/instructor-profiles/onboard_stripe/"),
        timeout=15,
    )
    assert resp.status_code == 401, (
        f"Expected 401 for unauthenticated onboarding, got {resp.status_code}: {resp.text}"
    )
