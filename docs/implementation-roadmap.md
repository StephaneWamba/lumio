# Lumio LMS — Implementation Roadmap

> Honest gap analysis as of 2026-03-20. 151 integration tests pass but major features are stubbed.

---

## What Is Actually Done vs Claimed

| Feature | Claimed | Reality |
|---------|---------|---------|
| Video upload pipeline | Phase 3 ✅ | HTTP 501 — never implemented |
| CloudFront signed URLs | Phase 3 ✅ | HTTP 501 — never implemented |
| Email verification | Phase 1 ✅ | Returns 200, sends nothing |
| Password reset | Phase 1 ✅ | Returns 200, sends nothing |
| Stripe payments | Phase 9 ✅ | Local state machine only, no Stripe API calls |
| Certificate PDF | Phase 7 ✅ | `.format()` string, no WeasyPrint |
| Email drip delivery | Phase 8 ✅ | Templates exist, no Resend calls |
| Drip unlock | Phase 6 ✅ | Marks released but never creates LessonUnlock |
| Celery Beat schedule | All phases | CELERY_BEAT_SCHEDULE is empty |
| Celery tasks | All phases | Zero tasks.py files exist |
| Adaptive quiz engine | Phase 5 ✅ | Static question order, no concept tagging |

---

## Roadmap: Implement Everything

### Step 1 — Celery Task Infrastructure (Prerequisite for everything)
**All async features depend on this. Do first.**

- Create `apps/{media,notifications,certificates,cohorts,assessments}/tasks.py`
- Add `CELERY_BEAT_SCHEDULE` to `config/settings/base.py`:
  - `drip_unlock_scanner` — hourly
  - `certificate_completion_check` — every 15 min
  - `email_reengagement_scanner` — daily
  - `analytics_refresh` — hourly
- Write unit tests for each task (TDD: test task logic, mock external calls)

---

### Step 2 — Phase 1 Completion: Email Auth Flows
**Files:** `apps/users/views.py`, new `apps/users/tasks.py`, new `apps/users/tokens.py`

#### 2a — Password Reset (lines 270, 290 in users/views.py)
- Generate time-limited token via `django.contrib.auth.tokens.PasswordResetTokenGenerator`
- Store token hash in Redis (TTL 1h)
- Call Resend API to send reset link
- `PasswordResetConfirmView`: validate token from Redis, call `user.set_password()`
- Tests: token generation, expiry, invalid token rejection, actual password change

#### 2b — Email Verification (lines 61, 310 in users/views.py)
- Generate UUID token on register, store in Redis (TTL 24h)
- Call Resend API with verification link
- `EmailVerificationView`: validate token, set `user.is_email_verified = True`
- Gate certain API actions on `is_email_verified`
- Tests: token sent on register, verification marks user verified, expired token rejected

#### 2c — Resend Client Wrapper
- Create `apps/core/email.py` with `send_transactional_email(to, subject, html)` using Resend SDK
- Used by password reset, email verify, notifications, certificates

---

### Step 3 — Phase 3: Video Pipeline
**Files:** `apps/media/views.py`, `apps/media/tasks.py`

#### 3a — Presigned S3 Upload (line 66 in media/views.py)
- `initiate_upload()`: generate presigned PUT URL via `boto3.client('s3').generate_presigned_url()`
- Return: `{ upload_url, video_id, expires_in }` — remove HTTP 501
- Frontend uploads directly to S3 (Django never touches bytes)
- Tests: presigned URL format, bucket/key correctness, expiry

#### 3b — FFmpeg Transcoding Task (apps/media/tasks.py)
- `transcode_video(video_id)` Celery task:
  - Download from S3 raw bucket
  - Run FFmpeg: 1080p/720p/480p MP4 → HLS segmentation → thumbnail
  - Upload HLS segments + manifest to S3 processed bucket
  - Upload thumbnail to assets bucket
  - Update `VideoFile.status = 'ready'`, set `hls_manifest_key`
  - Full retry with exponential backoff (max 3 attempts)
  - Dead letter: set `status = 'failed'` on final failure
- Wire S3 event notification → Celery task (or webhook endpoint)
- Tests: mock S3/FFmpeg, verify state transitions, retry behavior

#### 3c — CloudFront Signed URL (line 141 in media/views.py)
- `get_video_url()`: generate signed CloudFront URL (5-min expiry)
  - Use `CloudFront.generate_presigned_url()` or `botocore.signers.CloudFrontSigner`
  - Requires: `CLOUDFRONT_PRIVATE_KEY` (RSA PEM), `CLOUDFRONT_KEY_PAIR_ID`
  - Check enrollment before issuing URL
- Cache signed URL in Redis (4-min TTL, slightly under 5-min expiry)
- Remove HTTP 501 response
- Tests: URL includes signature, expiry enforced, unenrolled student gets 403

---

### Step 4 — Phase 5 Completion: Adaptive Quiz Engine
**Files:** `apps/assessments/views.py`, `apps/assessments/models.py`, new `apps/assessments/adaptive.py`

#### 4a — Concept Tagging Model
- Add `concept_tags` field to `Question` model (M2M or ArrayField)
- Migration
- Tests: questions tagged correctly

#### 4b — Per-Concept Performance Tracking
- After each quiz submission, calculate per-concept score
- Store in `AttemptConceptScore(attempt, concept, score_pct)` model
- Aggregate across attempts for `EnrollmentConceptProfile(enrollment, concept, avg_score)`

#### 4c — Adaptive Question Selection
- In `start_attempt()`, implement seeded RNG: `random.seed(hash(f"{enrollment_id}{attempt_number}"))`
- Weight question selection: higher probability for concepts where `avg_score < 70%`
- Replace static question list with weighted selection
- Tests: same seed → same questions (deterministic), weak concepts appear more often

#### 4d — "Review These Topics" Surfacing
- After failed attempt, return list of weak concepts in submit response
- Tests: failed attempt response contains concept recommendations

---

### Step 5 — Phase 6 Completion: Drip Unlock
**Files:** `apps/cohorts/views.py` (line 147), new `apps/cohorts/tasks.py`

#### 5a — Fix release_pending() to Create LessonUnlock Records
- After marking `DripSchedule.is_released = True`, bulk-create `LessonUnlock` records
- `LessonUnlock(enrollment, lesson, unlocked_at)` — one per enrolled student
- Use `SELECT FOR UPDATE` on cohort to prevent race condition
- Tests: unlock creates correct number of LessonUnlock records

#### 5b — Celery Beat Hourly Scanner
- `apps/cohorts/tasks.py`: `scan_and_release_drip()` task
- Add to `CELERY_BEAT_SCHEDULE`: `every=crontab(minute=0)` (hourly)
- Tests: task called → correct lessons unlocked

#### 5c — Lesson Access Gating
- In `LessonViewSet.retrieve()`, check `LessonUnlock` exists for student before returning content
- Tests: locked lesson → 403, unlocked → 200

---

### Step 6 — Phase 7 Completion: Certificate PDF Generation
**Files:** `apps/certificates/views.py` (line 172), new `apps/certificates/tasks.py`

#### 6a — WeasyPrint HTML→PDF
- Replace `.format()` placeholder with real WeasyPrint render:
  ```python
  from weasyprint import HTML
  pdf_bytes = HTML(string=rendered_html).write_pdf()
  ```
- Upload `pdf_bytes` to S3 assets bucket: `certificates/{uuid}.pdf`
- Store S3 key in `EarnedCertificate.pdf_s3_key`
- Tests: PDF bytes non-empty, S3 upload called with correct key

#### 6b — Async Certificate Generation (Celery Task)
- `apps/certificates/tasks.py`: `generate_certificate(enrollment_id)` task
- Triggered when course completion detected (from progress events)
- Completion detection: Celery Beat periodic task `check_completions()` every 15 min
  - Query enrollments where `progress_percentage = 100` and no certificate yet
- Tests: completion triggers task, task generates PDF, email sent

#### 6c — Certificate Email Delivery
- After PDF generated, call Resend to email student with PDF attached
- Include public verification URL (`/api/v1/certificates/verify/{uuid}/`)
- Tests: email called with correct attachment

#### 6d — Public Verification Endpoint
- `CertificateVerifyView` (already exists?) — verify UUID slug, return certificate info
- Must be public (no auth)
- Tests: valid UUID → cert info, invalid UUID → 404

---

### Step 7 — Phase 8 Completion: Email Drip Campaigns
**Files:** `apps/notifications/views.py`, new `apps/notifications/tasks.py`

#### 7a — Resend Email Delivery
- Create `apps/notifications/tasks.py`: `send_notification_email(notification_id)` task
- On Notification creation (signal or explicit call), if `email_enabled` in preferences → dispatch task
- Task: render template with Jinja2, call `send_transactional_email()`
- Track delivery in `NotificationLog`
- Tests: task called on notification create, Resend called with rendered template

#### 7b — On-Enrollment Email Scheduling
- When student enrolls, check `EmailSequence` for the course
- For each `TriggerRule` with time delay: schedule Celery task with `apply_async(countdown=delay_seconds)`
- Tests: enrollment → correct tasks scheduled with correct ETAs

#### 7c — Re-Engagement Daily Scanner
- `apps/notifications/tasks.py`: `scan_reengagement()` task
- Daily Celery Beat: find students inactive > 7 days with incomplete courses
- Send re-engagement email via Resend
- Tests: inactive student → email queued, active student → no email

#### 7d — Jinja2 Template Preview Endpoint
- `NotificationTemplateViewSet.preview()` action
- Render template with sample variables, return HTML
- Tests: preview renders correct variables

---

### Step 8 — Phase 9 Completion: Stripe Payments
**Files:** `apps/payments/views.py`, new `apps/payments/tasks.py`, new `apps/payments/webhooks.py`

#### 8a — Stripe Connect Instructor Onboarding (line 219 in users/views.py)
- `onboard_stripe()`: call `stripe.AccountLink.create()` with `type='account_onboarding'`
- Return actual Stripe OAuth URL (not placeholder message)
- Store `stripe_account_id` on `InstructorProfile`
- Tests: returns URL, URL contains Stripe domain

#### 8b — PaymentIntent Creation (line 79 in payments/views.py)
- `initiate_payment()`: call `stripe.PaymentIntent.create(amount, currency, application_fee_amount, transfer_data={'destination': instructor.stripe_account_id})`
- Return `client_secret` to frontend (for Stripe.js)
- Store `stripe_payment_intent_id` on Payment
- Tests: PaymentIntent created with correct fee split, client_secret returned

#### 8c — Webhook Handler
- New `apps/payments/webhooks.py`: handle `payment_intent.succeeded`, `payment_intent.payment_failed`, `charge.refunded`
- Verify webhook signature via `stripe.Webhook.construct_event()`
- Idempotent: check if Payment already in correct state before updating
- Tests: valid webhook → state updated, invalid signature → 400, replay → idempotent

#### 8d — Refund via Stripe (line 191 in payments/views.py)
- `refund()`: call `stripe.Refund.create(payment_intent=payment.stripe_payment_intent_id)`
- Tests: refund calls Stripe, local state updated

---

### Step 9 — Analytics Caching
**Files:** `apps/analytics/views.py`

- Add Redis caching (1h TTL) to expensive aggregation endpoints:
  ```python
  @method_decorator(cache_page(60 * 60))
  ```
- Or manual: `cache.get(cache_key)` / `cache.set(cache_key, data, 3600)`
- `recalculate()` action should invalidate cache
- Tests: second call returns cached response, recalculate clears cache

---

### Step 10 — Integration Test Improvements
**Files:** `tests/integration/`

- Replace all status-code-only tests with data assertions
- Remove conditional `pytest.skip()` — test the expected behavior instead
- Add tests for: adaptive quiz question seeding, drip unlock creates LessonUnlock, certificate PDF non-empty, payment webhook handling
- Verify Stripe/Resend calls in integration tests via response body assertions (not mocks)

---

## Priority Order

| Priority | Step | Effort | Impact |
|----------|------|--------|--------|
| 1 | Celery infrastructure | S | Blocks everything async |
| 2 | Phase 3: Video pipeline | L | Core product feature, students can't watch videos |
| 3 | Phase 1: Email auth | M | Security risk (fake 200s) |
| 4 | Phase 9: Stripe | L | No revenue without it |
| 5 | Phase 7: Certificates | M | Spec feature, WeasyPrint ready |
| 6 | Phase 8: Email drip | M | Retention feature |
| 7 | Phase 6: Drip unlock | S | Model mostly done |
| 8 | Phase 5: Adaptive quiz | M | Spec requirement |
| 9 | Analytics caching | S | Performance |
| 10 | Test improvements | M | Quality |

---

## External Dependencies to Configure in Production

| Service | Env Var | Used For |
|---------|---------|---------|
| Resend | `RESEND_API_KEY` | Email verify, password reset, drip, certificates |
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | Payments, Connect onboarding |
| S3 | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_RAW_BUCKET`, `S3_PROCESSED_BUCKET`, `S3_ASSETS_BUCKET` | Video upload, PDF storage |
| CloudFront | `CLOUDFRONT_DOMAIN`, `CLOUDFRONT_KEY_PAIR_ID`, `CLOUDFRONT_PRIVATE_KEY` | Signed video URLs |
| Redis | `REDIS_URL` | Celery broker, cache, rate limiting |
