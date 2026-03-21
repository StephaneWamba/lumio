"""
End-to-end journey integration tests for Lumio LMS.

Each test exercises a complete feature flow from the perspective of an API
client: setup → action → downstream effect verified. No mocks. No stubs.
All requests hit the live production ALB.

Run with:
    pytest tests/integration/test_e2e_journeys.py -v -m integration --no-cov
"""

import hashlib
import hmac
import json
import time as _time

import pytest
import requests

from .conftest import AuthedClient, TEST_RUN_ID, api, login, register_user

pytestmark = pytest.mark.integration


def test_full_learning_journey(student_client, published_course):
    """
    Journey: enroll → mark lesson viewed → mark lesson completed → progress record verified.

    The published_course has exactly 1 lesson. Completing that 1 lesson should
    produce a LessonProgress record with is_completed=True or a completed_at timestamp.
    """
    course_id = published_course["id"]
    lesson_id = published_course["_lesson_id"]

    # 1. Enroll (or accept already-enrolled)
    r = student_client.post(
        "/api/v1/enrollments/enrollments/enroll/",
        json={"course_id": course_id},
    )
    assert r.status_code in (201, 400), f"Enroll failed: {r.status_code} {r.text}"

    # 2. Find enrollment id
    list_r = student_client.get("/api/v1/enrollments/enrollments/")
    assert list_r.status_code == 200
    items = list_r.json()
    items = items if isinstance(items, list) else items.get("results", [])
    enrollment = next(
        (
            e for e in items
            if e.get("course") == course_id
            or (isinstance(e.get("course"), dict) and e["course"].get("id") == course_id)
        ),
        None,
    )
    assert enrollment is not None, f"Could not find enrollment for course {course_id}: {items}"
    enrollment_id = enrollment["id"]

    # 3. Mark lesson viewed
    r = student_client.post(
        f"/api/v1/enrollments/enrollments/{enrollment_id}/mark_lesson_viewed/",
        json={"lesson_id": lesson_id},
    )
    assert r.status_code == 200, f"mark_lesson_viewed failed: {r.status_code} {r.text}"

    # 4. Mark lesson completed
    r = student_client.post(
        f"/api/v1/enrollments/enrollments/{enrollment_id}/mark_lesson_completed/",
        json={"lesson_id": lesson_id},
    )
    assert r.status_code == 200, f"mark_lesson_completed failed: {r.status_code} {r.text}"

    # 5. Verify progress record exists and shows completion
    r = student_client.get(
        f"/api/v1/enrollments/enrollments/{enrollment_id}/progress/"
    )
    assert r.status_code == 200, f"GET progress failed: {r.status_code} {r.text}"
    progress_list = r.json()
    assert isinstance(progress_list, list), f"Expected list, got: {type(progress_list)}"

    lesson_progress = next(
        (
            p for p in progress_list
            if p.get("lesson") == lesson_id or p.get("lesson_id") == lesson_id
        ),
        None,
    )
    assert lesson_progress is not None, (
        f"No progress record found for lesson {lesson_id}: {progress_list}"
    )
    assert (
        lesson_progress.get("is_completed") is True
        or lesson_progress.get("completed_at") is not None
    ), f"Lesson not marked complete in progress record: {lesson_progress}"


def test_full_stripe_payment_journey(instructor_client, student_client):
    """
    Journey: create course with price → student initiates payment →
    verify real Stripe PaymentIntent exists → simulate webhook →
    student is enrolled.
    """
    import os
    import stripe

    stripe_secret = os.environ.get("STRIPE_SECRET_KEY")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not stripe_secret or not webhook_secret:
        pytest.skip("STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET not set")
    stripe.api_key = stripe_secret

    # 1. Create a fresh course
    r = instructor_client.post(
        "/api/v1/courses/courses/",
        json={
            "title": f"Stripe E2E Course {TEST_RUN_ID}",
            "description": "Payment journey test course.",
            "short_description": "Stripe E2E.",
            "difficulty": "beginner",
            "language": "en",
        },
    )
    assert r.status_code == 201, f"Course creation failed: {r.status_code} {r.text}"
    course_id = r.json()["id"]
    instructor_client.get(f"/api/v1/courses/courses/{course_id}/publish/")

    # 2. Create a price
    r = instructor_client.post(
        "/api/v1/payments/prices/",
        json={
            "course_id": course_id,
            "amount": "9.99",
            "currency": "USD",
            "price_type": "one_time",
            "is_active": True,
        },
    )
    assert r.status_code == 201, f"Price creation failed: {r.status_code} {r.text}"

    # 3. Initiate payment as student — creates real Stripe PaymentIntent
    r = student_client.post(
        "/api/v1/payments/payments/initiate_payment/",
        json={"course_id": course_id},
    )
    assert r.status_code == 201, f"initiate_payment failed: {r.status_code} {r.text}"
    data = r.json()
    assert "client_secret" in data, f"Missing client_secret: {data}"
    assert "transaction_id" in data, f"Missing transaction_id: {data}"
    intent_id = data["transaction_id"]
    assert intent_id.startswith("pi_"), f"Expected Stripe PI id, got: {intent_id}"

    # 4. Verify PaymentIntent exists on Stripe
    intent = stripe.PaymentIntent.retrieve(intent_id)
    assert intent.amount == 999, f"Expected 999 cents, got: {intent.amount}"
    assert intent.currency == "usd"

    # 5. Find the payment DB id
    list_r = student_client.get("/api/v1/payments/payments/")
    payments = list_r.json()
    payments = payments if isinstance(payments, list) else payments.get("results", [])
    matching = [p for p in payments if p.get("transaction_id") == intent_id]
    assert matching, f"Could not find payment with transaction_id={intent_id}"
    payment_db_id = matching[0]["id"]

    # 6. Simulate payment_intent.succeeded webhook
    payload_dict = {
        "id": f"evt_e2e_{TEST_RUN_ID}",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": intent_id,
                "metadata": {"payment_id": str(payment_db_id)},
            }
        },
    }
    payload = json.dumps(payload_dict).encode()
    ts = int(_time.time())
    signed = f"{ts}.{payload.decode()}"
    sig = hmac.new(
        webhook_secret.encode(),
        signed.encode(),
        hashlib.sha256,
    ).hexdigest()

    webhook_r = requests.post(
        api("/api/v1/payments/webhook/"),
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": f"t={ts},v1={sig}",
        },
        timeout=30,
    )
    assert webhook_r.status_code == 200, f"Webhook failed: {webhook_r.status_code} {webhook_r.text}"

    # 7. Verify student is now enrolled
    list_r = student_client.get("/api/v1/enrollments/enrollments/")
    assert list_r.status_code == 200
    items = list_r.json()
    items = items if isinstance(items, list) else items.get("results", [])
    enrolled_ids = [
        e["course"] if not isinstance(e.get("course"), dict) else e["course"]["id"]
        for e in items
    ]
    assert course_id in enrolled_ids, (
        f"Student not enrolled after webhook. Enrolled courses: {enrolled_ids}"
    )


def test_full_video_pipeline_journey(instructor_client, published_course):
    """
    Journey: initiate_upload → get presigned S3 URL → PUT tiny file to S3 →
    trigger_transcode → poll status endpoint.
    """
    lesson_id = published_course["_lesson_id"]

    # 1. Initiate upload
    r = instructor_client.post(
        "/api/v1/media/videos/initiate_upload/",
        json={
            "lesson_id": lesson_id,
            "file_name": f"e2e_test_{TEST_RUN_ID}.mp4",
            "file_size_bytes": 1024,
        },
    )
    assert r.status_code == 200, f"initiate_upload failed: {r.status_code} {r.text}"
    data = r.json()
    assert "upload_url" in data, f"Missing upload_url: {data}"
    assert "video_id" in data, f"Missing video_id: {data}"
    upload_url = data["upload_url"]
    video_id = data["video_id"]
    assert upload_url.startswith("https://"), f"upload_url not HTTPS: {upload_url}"

    # 2. PUT a tiny fake payload to S3
    tiny_payload = b"\x00" * 1024
    put_r = requests.put(upload_url, data=tiny_payload, timeout=30)
    assert put_r.status_code == 200, (
        f"S3 presigned PUT failed: {put_r.status_code} {put_r.text}"
    )

    # 3. Trigger transcoding
    r = instructor_client.post(f"/api/v1/media/videos/{video_id}/trigger_transcode/")
    assert r.status_code in (200, 202), (
        f"trigger_transcode failed: {r.status_code} {r.text}"
    )
    trigger_data = r.json()
    assert trigger_data.get("status") in ("queued", "already_completed", "already_processing"), (
        f"Unexpected trigger_transcode status: {trigger_data}"
    )

    # 4. Poll status
    r = instructor_client.get(f"/api/v1/media/videos/{video_id}/status/")
    assert r.status_code == 200, f"GET status failed: {r.status_code} {r.text}"
    status_data = r.json()
    assert "status" in status_data, f"Missing 'status': {status_data}"
    assert status_data["status"] in ("pending", "processing", "completed", "failed"), (
        f"Unknown video status: {status_data['status']}"
    )
    assert "hls_ready" in status_data, f"Missing 'hls_ready': {status_data}"


def test_full_certificate_issuance_and_public_verify(
    instructor_client, student_client, published_course, student_enrollment
):
    """
    Journey: create template → create award → issue certificate →
    public /verify/<cert_num>/ returns student name and course title without auth.
    """
    course_id = published_course["id"]
    enrollment_id = student_enrollment["id"]

    # 1. Create certificate template (idempotent)
    r = instructor_client.post(
        "/api/v1/certificates/templates/",
        json={
            "course_id": course_id,
            "name": f"E2E Certificate {TEST_RUN_ID}",
            "content": "Congratulations {student_name} on completing {course_title}!",
            "is_active": True,
        },
    )
    assert r.status_code in (201, 400), f"Template creation failed: {r.status_code} {r.text}"

    # 2. Create award criteria (0% so any student qualifies)
    r = instructor_client.post(
        "/api/v1/certificates/awards/",
        json={
            "course_id": course_id,
            "min_completion_percentage": 0,
            "min_quiz_score": None,
        },
    )
    assert r.status_code in (201, 400), f"Award creation failed: {r.status_code} {r.text}"

    # 3. Issue certificate
    r = instructor_client.post(
        "/api/v1/certificates/earned/issue_for_enrollment/",
        json={"enrollment_id": enrollment_id},
    )
    assert r.status_code in (201, 400), (
        f"issue_for_enrollment failed: {r.status_code} {r.text}"
    )

    if r.status_code == 400 and "already issued" in r.text.lower():
        list_r = student_client.get("/api/v1/certificates/earned/")
        assert list_r.status_code == 200
        items = list_r.json()
        items = items if isinstance(items, list) else items.get("results", [])
        assert items, "Expected at least one certificate but list is empty"
        cert_number = items[0]["certificate_number"]
    else:
        cert_data = r.json()
        assert "certificate_number" in cert_data, f"Missing certificate_number: {cert_data}"
        cert_number = cert_data["certificate_number"]

    # 4. Hit public verify endpoint WITHOUT auth
    verify_r = requests.get(
        api(f"/api/v1/certificates/verify/{cert_number}/"),
        timeout=30,
    )
    assert verify_r.status_code == 200, (
        f"Public certificate verify failed: {verify_r.status_code} {verify_r.text}"
    )
    verify_data = verify_r.json()
    assert "student_name" in verify_data, f"Missing student_name: {verify_data}"
    assert "course_title" in verify_data, f"Missing course_title: {verify_data}"
    assert verify_data.get("is_valid") is True, f"is_valid not True: {verify_data}"


def test_full_cohort_drip_unlock_journey(instructor_client, student_client, published_course):
    """
    Journey: create cohort → student joins → create drip schedule (day=0) →
    manually release → lesson unlock record exists.
    """
    from uuid import uuid4

    course_id = published_course["id"]
    lesson_id = published_course["_lesson_id"]
    unique = uuid4().hex[:6]

    # 1. Create cohort
    r = instructor_client.post(
        "/api/v1/cohorts/cohorts/",
        json={
            "course": course_id,
            "name": f"E2E Drip Cohort {unique}",
            "start_date": "2026-03-21",
            "max_students": 10,
            "is_open": True,
        },
    )
    assert r.status_code == 201, f"Cohort creation failed: {r.status_code} {r.text}"
    cohort_id = r.json()["id"]

    # 2. Student joins cohort
    r = student_client.post(
        f"/api/v1/cohorts/cohorts/{cohort_id}/join/",
        json={},
    )
    assert r.status_code in (200, 201, 400), f"Cohort join failed: {r.status_code} {r.text}"
    if r.status_code == 400:
        assert "member" in r.text.lower() or "already" in r.text.lower(), (
            f"Unexpected 400 from join: {r.text}"
        )

    # 3. Create drip schedule for lesson on day 0
    r = instructor_client.post(
        "/api/v1/cohorts/drip-schedules/",
        json={"cohort": cohort_id, "lesson": lesson_id, "unlock_day": 0},
    )
    assert r.status_code in (201, 400), f"Drip schedule creation failed: {r.status_code} {r.text}"
    if r.status_code == 201:
        schedule_id = r.json()["id"]
    else:
        list_r = instructor_client.get(f"/api/v1/cohorts/drip-schedules/?cohort={cohort_id}")
        assert list_r.status_code == 200
        schedules = list_r.json()
        schedules = schedules if isinstance(schedules, list) else schedules.get("results", [])
        matching = [
            s for s in schedules
            if s.get("lesson") == lesson_id or s.get("lesson_id") == lesson_id
        ]
        assert matching, f"No drip schedule for lesson {lesson_id} in cohort {cohort_id}"
        schedule_id = matching[0]["id"]

    # 4. Manually release
    r = instructor_client.post(
        f"/api/v1/cohorts/drip-schedules/{schedule_id}/manually_release/",
        json={},
    )
    assert r.status_code in (200, 201), f"manually_release failed: {r.status_code} {r.text}"
    assert r.json().get("is_released") is True, f"is_released not True: {r.json()}"

    # 5. Verify lesson unlock exists
    r = student_client.get(f"/api/v1/cohorts/lesson-unlocks/?cohort={cohort_id}")
    assert r.status_code == 200, f"GET lesson-unlocks failed: {r.status_code} {r.text}"
    unlocks = r.json()
    unlocks = unlocks if isinstance(unlocks, list) else unlocks.get("results", [])
    unlocked_ids = [u.get("lesson") or u.get("lesson_id") for u in unlocks]
    assert lesson_id in unlocked_ids, (
        f"Lesson {lesson_id} not unlocked. Unlocked: {unlocked_ids}"
    )


def test_full_quiz_attempt_journey(instructor_client, student_client, published_course, student_enrollment):
    """
    Journey: create quiz → create question → start attempt → submit answer → score returned.
    """
    lesson_id = published_course["_lesson_id"]

    # 1. Create quiz (idempotent — 400 if exists)
    r = instructor_client.post(
        "/api/v1/assessments/quizzes/",
        json={
            "lesson": lesson_id,
            "title": f"E2E Quiz {TEST_RUN_ID}",
            "description": "Journey test quiz.",
            "passing_score": "0.00",
            "max_attempts": 10,
            "allow_retake": True,
            "time_limit_minutes": None,
        },
    )
    assert r.status_code in (201, 400), f"Quiz creation failed: {r.status_code} {r.text}"
    if r.status_code == 201:
        quiz_id = r.json()["id"]
    else:
        list_r = instructor_client.get(f"/api/v1/assessments/quizzes/?lesson={lesson_id}")
        assert list_r.status_code == 200
        quizzes = list_r.json()
        quizzes = quizzes if isinstance(quizzes, list) else quizzes.get("results", [])
        assert quizzes, f"No quiz found for lesson {lesson_id}"
        quiz_id = quizzes[0]["id"]

    # 2. Create a question
    r = instructor_client.post(
        "/api/v1/assessments/questions/",
        json={
            "quiz": quiz_id,
            "text": f"E2E Question {TEST_RUN_ID}: What is 1 + 1?",
            "question_type": "multiple_choice",
            "points": "10.00",
            "order": 1,
            "options": [
                {"text": "1", "is_correct": False},
                {"text": "2", "is_correct": True},
                {"text": "3", "is_correct": False},
            ],
        },
    )
    if r.status_code == 405:
        pytest.skip("Question creation endpoint not available (405)")
    assert r.status_code in (200, 201), f"Question creation failed: {r.status_code} {r.text}"
    question = r.json()
    question_id = question["id"]
    correct_option = next(
        (opt for opt in question.get("options", []) if opt.get("is_correct")),
        None,
    )

    # 3. Start attempt
    r = student_client.post(
        "/api/v1/assessments/attempts/",
        json={"quiz": quiz_id},
    )
    assert r.status_code == 201, f"Start attempt failed: {r.status_code} {r.text}"
    attempt_id = r.json()["id"]

    # 4. Submit answer
    answers = [{"question_id": question_id}]
    if correct_option:
        answers[0]["selected_option_id"] = correct_option["id"]
    else:
        answers[0]["text_answer"] = "2"

    r = student_client.post(
        f"/api/v1/assessments/attempts/{attempt_id}/submit/",
        json={"answers": answers},
    )
    assert r.status_code == 200, f"Submit attempt failed: {r.status_code} {r.text}"
    result = r.json()

    # 5. Verify score present
    assert (
        "score" in result or "total_score" in result or "percentage" in result
    ), f"No score field in submit response: {result}"


def test_stripe_fee_split_with_connected_instructor(instructor_client, student_client):
    """
    Journey: instructor onboards Stripe → course with price → student initiates payment →
    verify application_fee_amount on Stripe PI.
    """
    import os
    import stripe

    stripe_secret = os.environ.get("STRIPE_SECRET_KEY")
    platform_pct = float(os.environ.get("STRIPE_PLATFORM_SHARE_PCT", "20"))
    if not stripe_secret:
        pytest.skip("STRIPE_SECRET_KEY not set")
    stripe.api_key = stripe_secret

    # 1. Onboard instructor (idempotent)
    r = instructor_client.post("/api/v1/auth/instructor-profiles/onboard_stripe/")
    assert r.status_code == 200, f"Stripe onboarding failed: {r.status_code} {r.text}"
    assert "onboarding_url" in r.json(), f"Missing onboarding_url: {r.json()}"

    # 2. Create fresh course with price
    r = instructor_client.post(
        "/api/v1/courses/courses/",
        json={
            "title": f"Fee Split Course {TEST_RUN_ID}",
            "description": "Fee split test.",
            "short_description": "Fee split.",
            "difficulty": "beginner",
            "language": "en",
        },
    )
    assert r.status_code == 201
    course_id = r.json()["id"]
    instructor_client.get(f"/api/v1/courses/courses/{course_id}/publish/")

    r = instructor_client.post(
        "/api/v1/payments/prices/",
        json={
            "course_id": course_id,
            "amount": "50.00",
            "currency": "USD",
            "price_type": "one_time",
            "is_active": True,
        },
    )
    assert r.status_code == 201, f"Price creation failed: {r.status_code} {r.text}"

    # 3. Initiate payment
    r = student_client.post(
        "/api/v1/payments/payments/initiate_payment/",
        json={"course_id": course_id},
    )
    assert r.status_code == 201, f"initiate_payment failed: {r.status_code} {r.text}"
    intent_id = r.json()["transaction_id"]

    # 4. Verify fee on Stripe (if instructor completed onboarding)
    intent = stripe.PaymentIntent.retrieve(intent_id)
    if intent.application_fee_amount is not None:
        expected_fee = int(5000 * platform_pct / 100)
        assert intent.application_fee_amount == expected_fee, (
            f"Expected fee {expected_fee}, got {intent.application_fee_amount}"
        )
    # None is acceptable if Stripe account not fully verified in test mode
