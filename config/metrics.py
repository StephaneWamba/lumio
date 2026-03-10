"""Prometheus custom metrics for Lumio LMS."""

from prometheus_client import Counter, Histogram, Gauge

# ── Enrollments ───────────────────────────────────────────────────────────────
enrollment_created = Counter(
    "lumio_enrollments_created_total",
    "Total enrollments created",
    ["course_id"],
)

enrollment_completed = Counter(
    "lumio_enrollments_completed_total",
    "Total enrollments completed",
    ["course_id"],
)

# ── Quiz attempts ─────────────────────────────────────────────────────────────
quiz_attempt_started = Counter(
    "lumio_quiz_attempts_started_total",
    "Quiz attempts started",
    ["quiz_id"],
)

quiz_attempt_passed = Counter(
    "lumio_quiz_attempts_passed_total",
    "Quiz attempts that passed",
    ["quiz_id"],
)

quiz_attempt_failed = Counter(
    "lumio_quiz_attempts_failed_total",
    "Quiz attempts that failed",
    ["quiz_id"],
)

# ── Transcoding ───────────────────────────────────────────────────────────────
transcoding_job_started = Counter(
    "lumio_transcoding_jobs_started_total",
    "Transcoding jobs started",
)

transcoding_job_completed = Counter(
    "lumio_transcoding_jobs_completed_total",
    "Transcoding jobs completed successfully",
)

transcoding_job_failed = Counter(
    "lumio_transcoding_jobs_failed_total",
    "Transcoding jobs that failed",
)

transcoding_duration_seconds = Histogram(
    "lumio_transcoding_duration_seconds",
    "Transcoding job duration in seconds",
    buckets=[30, 60, 120, 300, 600, 1200, 3600],
)

# ── Certificates ──────────────────────────────────────────────────────────────
certificate_issued = Counter(
    "lumio_certificates_issued_total",
    "Certificates issued",
)

# ── Payments ──────────────────────────────────────────────────────────────────
payment_initiated = Counter(
    "lumio_payments_initiated_total",
    "Payment intents initiated",
)

payment_completed = Counter(
    "lumio_payments_completed_total",
    "Payments completed successfully",
)

payment_failed = Counter(
    "lumio_payments_failed_total",
    "Payments that failed",
)

# ── Celery queue depth (Gauge, updated by periodic task) ─────────────────────
celery_queue_depth = Gauge(
    "lumio_celery_queue_depth",
    "Number of tasks waiting in queue",
    ["queue_name"],
)

# ── API response time ─────────────────────────────────────────────────────────
api_request_duration_seconds = Histogram(
    "lumio_api_request_duration_seconds",
    "API endpoint response time",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# ── Active users (updated by periodic Beat task) ─────────────────────────────
active_users_gauge = Gauge(
    "lumio_active_users",
    "Users active in the last 15 minutes",
)
