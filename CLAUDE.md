# Lumio LMS — Claude Code Instructions

## Project Overview

A production-grade Learning Management System. Instructors create and sell courses with video content, quizzes, and drip scheduling. Students learn, track progress, and earn verifiable certificates. The engineering showcase is the async pipeline underneath: video transcoding, event-sourced progress, adaptive quiz engine, certificate generation, email drip campaigns.

Full spec: `specs.md`

---

## Non-Negotiable Rules

- **Never weaken a feature.** If the spec says adaptive quiz, build adaptive quiz — not a basic quiz with a comment saying "adaptive later."
- **No local-only work.** Every phase ships to production (AWS ECS) before moving to the next. CI/CD is wired from day one.
- **Frontend comes last.** The React app is Phase 12. Do not suggest or build frontend code until Phase 11 (hardening) is complete and the OpenAPI spec is frozen.
- **Terraform owns all infrastructure.** Never create AWS resources manually. All infra changes go through `terraform/`.
- **Tests are not optional.** Every model, service, and API endpoint gets pytest coverage before the phase is marked done.

---

## Tech Stack

### Backend
- **Runtime:** Python 3.12 + Django 5.x
- **API:** Django REST Framework (versioned: `/api/v1/`)
- **Auth:** `djangorestframework-simplejwt` (JWT, 15min access / 7-day rotating refresh) + `social-django` (Google, GitHub OAuth2)
- **Permissions:** `django-guardian` for object-level permissions + custom DRF permission classes
- **Background jobs:** Celery 5.x with Redis broker, Celery Beat for periodic tasks
- **PDF:** WeasyPrint (server-side HTML → PDF certificate rendering)
- **Email:** Resend (primary) via their Python SDK
- **Search:** PostgreSQL full-text search (`tsvector` + `GIN` index) — no Elasticsearch
- **Logging:** Structlog (structured JSON to stdout)
- **Error tracking:** Sentry (Django + Celery integration)
- **API docs:** drf-spectacular (OpenAPI 3.0)

### Databases
- **Primary:** PostgreSQL 16 (AWS RDS)
- **Cache / Broker:** Redis 7 (AWS ElastiCache)

### Media
- **Raw uploads:** AWS S3 bucket `lumio-raw-uploads` (presigned PUT, frontend uploads directly)
- **Processed media:** AWS S3 bucket `lumio-processed-media` (behind CloudFront, signed URLs only)
- **Assets:** AWS S3 bucket `lumio-assets` (thumbnails, avatars, certificate PDFs)
- **CDN:** AWS CloudFront (signed URLs enforced — no unsigned access to processed media)
- **Transcoding:** FFmpeg inside a dedicated ECS container

### Infrastructure
- **Containers:** Docker (3 images: `lumio-app`, `lumio-celery`, `lumio-ffmpeg`)
- **Orchestration:** AWS ECS Fargate
- **IaC:** Terraform (modules per service, `staging` + `production` environments)
- **CI/CD:** GitHub Actions → lint → typecheck → pytest → build → push ECR → terraform apply → ECS deploy
- **Registry:** AWS ECR

### Frontend (Phase 12 only)
- React 18 + TypeScript + Vite
- TanStack Query (React Query) for server state
- Tailwind CSS
- Video.js + HLS.js
- TipTap (rich text editor)
- @dnd-kit (drag-and-drop course builder)
- Stripe.js
- Deployed to Vercel

### Observability
- Prometheus + Grafana (ECS service)
- Celery Flower (ECS service, auth-gated)
- `django-prometheus` middleware
- CloudWatch alarms

---

## Django App Structure

```
lumio/
├── config/                  # settings/, urls.py, wsgi.py, asgi.py
│   ├── settings/
│   │   ├── base.py
│   │   ├── staging.py
│   │   └── production.py
├── apps/
│   ├── users/               # Custom User model, roles, OAuth
│   ├── courses/             # Course, Section, Lesson hierarchy
│   ├── media/               # MediaAsset, transcoding pipeline
│   ├── enrollments/         # Enrollment, ProgressEvent (event log)
│   ├── assessments/         # Quiz, Question, Attempt, adaptive engine
│   ├── cohorts/             # Cohort, DripRule, LessonDiscussion
│   ├── certificates/        # Certificate, PDF generation
│   ├── notifications/       # EmailSequence, TriggerRule, EmailDelivery
│   └── payments/            # Stripe Connect, PaymentIntent, Review
├── terraform/
│   ├── modules/
│   │   ├── networking/
│   │   ├── ecs/
│   │   ├── rds/
│   │   ├── elasticache/
│   │   ├── s3/
│   │   ├── cloudfront/
│   │   ├── ecr/
│   │   └── monitoring/
│   ├── environments/
│   │   ├── staging/
│   │   └── production/
│   └── main.tf
├── .github/
│   └── workflows/
│       └── ci-cd.yml
├── Dockerfile
├── Dockerfile.celery
├── Dockerfile.ffmpeg
├── docker-compose.yml
└── pyproject.toml
```

---

## Roadmap

### Phase 0 — Infrastructure & CI/CD Foundation
Terraform provisions all AWS resources. GitHub Actions pipeline wired. Django project scaffolded. Structlog + Sentry configured. Health check endpoint live on ECS.
**Done when:** `curl https://api.lumio.io/health/` returns 200 from ECS Fargate.

### Phase 1 — Identity, Auth & Permissions
Custom User model (email-based), JWT auth, OAuth2 (Google + GitHub), email verification, password reset, rate limiting. `django-guardian` installed and permission classes scaffolded.
**Done when:** Full auth flow end-to-end in production. All permission classes tested.

### Phase 2 — Content Management
Course/Section/Lesson hierarchy. Draft/published states at every level. Prerequisite logic (with cycle detection). Ordering system (contiguous integer reorder). Course Builder API (CRUD, reorder, bulk publish, duplicate). Django Admin for instructor approval and course moderation.
**Done when:** Instructor can create a full course hierarchy via API in production.

### Phase 3 — Media Pipeline
Presigned S3 upload flow (frontend uploads directly, Django never touches bytes). FFmpeg worker (ECS): 1080p/720p/480p MP4 → HLS segmentation → thumbnail. Full retry with exponential backoff + dead letter queue. Signed CloudFront URL generation (students never get raw URLs). Status polling endpoint.
**Done when:** Full pipeline working in production: upload → transcode → HLS → signed playback URL.

### Phase 4 — Enrollment & Event-Sourced Progress
Enrollment model (self-paced + cohort). Immutable ProgressEvent log (lesson_opened, video_progress, video_completed, quiz_submitted, lesson_completed). Duplicate event deduplication. Real-time progress calculation from event log. Periodic progress materialization into Redis cache. Lesson access gating (enrollment + prerequisite check).
**Done when:** Students enroll, open lessons, generate events, progress derived correctly.

### Phase 5 — Assessment: Full Quiz Engine with Adaptive Logic
Question types: MC, T/F, short answer, code snippet. Concept tagging. QuizAttempt recording. Per-concept performance tracking across attempts. Adaptive question selection (weighted by weak concepts, deterministic via seeded RNG: `hash(enrollment_id + attempt_number)`). "Review these topics" surfacing after failed attempt. Manual grading endpoint for short answer/code.
**Done when:** Full quiz flow in production including adaptive retry behaviour.

### Phase 6 — Cohorts & Drip Publishing
Cohort model (start date, enrollment cap). DripRule (unlock_day relative to cohort start). Periodic scanner pattern (Celery Beat hourly — NOT per-student tasks) for content unlock. LessonUnlock records bulk-created. Enrollment cap enforcement (SELECT FOR UPDATE). Per-lesson per-cohort discussion threads.
**Done when:** Cohort enrollment, drip unlock verified working. 10k-student scenario validated.

### Phase 7 — Certificate Generation
Completion detection (Celery Beat periodic). WeasyPrint HTML → PDF. S3 storage. UUID verification slug. Public verification endpoint. Email delivery with PDF attached.
**Done when:** Student completes course → PDF generated → email sent → verification URL live.

### Phase 8 — Email Drip Campaigns
EmailSequence + TriggerRule models. On-enrollment scheduling (Celery ETA for time-delay rules). Re-engagement periodic scanner (daily Celery Beat). Resend delivery. EmailDelivery tracking. Instructor template editor API (Jinja2, dynamic variables). Preview endpoint.
**Done when:** Full drip system working — enrollment triggers, time-delay, re-engagement.

### Phase 9 — Payments & Course Marketplace
Stripe Connect (Express) instructor onboarding. PaymentIntent with `application_fee_amount` (platform share) + `transfer_data.destination`. Webhook handler (idempotent). PostgreSQL full-text search on course catalog (GIN index). Ratings & reviews (completion-gated). Refund endpoint (admin-only).
**Done when:** Paid course purchase completes in production with revenue split to instructor.

### Phase 10 — Instructor Analytics & Corporate Manager
All aggregation queries live: enrollment over time, completion rate, avg quiz score per lesson, student drop-off by lesson, revenue breakdown, video engagement. Redis-cached (1h TTL). Corporate Manager bulk enrollment + team progress report.
**Done when:** All analytics endpoints returning real data in production.

### Phase 11 — Observability, Security Hardening & Load Testing
Prometheus + Grafana dashboards (API health, queue depth, transcoding throughput). Celery Flower deployed. `django-ratelimit` on auth + presigned URL + quiz endpoints. S3 bucket policies verified. CORS locked down. Load tests: 1k concurrent video streams, 10k cohort enrollments, concurrent quiz submissions.
**Done when:** Dashboards live. Load test results documented. No security findings.

### Phase 12 — Frontend
React 18 + TypeScript. Built against frozen OpenAPI spec. Pages in order: auth → catalog → enrollment/payment → learning interface → student dashboard → certificate page → course builder → quiz builder → instructor analytics → cohort management → email editor → admin panel.
**Done when:** Full application usable end-to-end in production.

---

## Key Engineering Decisions (Rationale)

| Decision | Rationale |
|----------|-----------|
| Event-sourced progress (immutable log) | Progress can never get out of sync. Trivially auditable. Handles duplicates and out-of-order events cleanly. |
| Periodic scanner for drip unlock | 10k simultaneous enrollments cannot create 10k Celery tasks. One periodic task scans all cohorts and bulk-creates unlocks. |
| Adaptive quiz RNG seeded by `hash(enrollment_id + attempt_number)` | Same student state → same questions. Deterministic, reproducible, fair. |
| Presigned S3 upload (frontend → S3 direct) | Django never handles multi-GB video bytes. No timeout risk, no bandwidth bottleneck. |
| Signed CloudFront URLs (5-min expiry) | Students cannot share video URLs. Every playback request goes through enrollment check first. |
| Separate FFmpeg ECS task definition | FFmpeg container is heavy (~300MB). Scales independently from API workers based on transcoding queue depth. |
| PostgreSQL FTS over Elasticsearch | Sufficient at this scale. Eliminates an entire infrastructure component. Revisit if course catalog exceeds 100k courses. |
| WeasyPrint over headless Chrome for PDFs | Lighter dependency, no browser process management, predictable output for structured certificate layout. |

---

## Code Conventions

- **Models:** Always define `__str__`, `Meta.ordering`, and `Meta.indexes` for any field used in frequent queries.
- **Querysets:** Never filter in views. Override `get_queryset()` in viewsets with enrollment/ownership checks.
- **Celery tasks:** All tasks must be idempotent. Check if work is already done before doing it.
- **Migrations:** Never edit a migration after it has been applied to staging or production. Create a new migration.
- **Secrets:** All credentials via environment variables. Never hardcode. AWS Secrets Manager in production (injected into ECS task environment by Terraform).
- **Tests:** Use `pytest-django` + `factory_boy` for fixtures. Mock S3/CloudFront/Stripe/Resend at the boundary. Never make real external calls in tests.
- **API versioning:** All routes under `/api/v1/`. When breaking changes needed, create `/api/v2/` namespace.
- **Logging:** Use `structlog.get_logger()`. Always include `user_id`, `course_id`, `task_id` in log context where applicable. Never log sensitive data (passwords, tokens, card numbers).

---

## Environment Variables (required)

```
DJANGO_SECRET_KEY
DJANGO_SETTINGS_MODULE          # config.settings.production
DATABASE_URL                    # postgres://...
REDIS_URL                       # redis://...
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
AWS_REGION
S3_RAW_BUCKET
S3_PROCESSED_BUCKET
S3_ASSETS_BUCKET
CLOUDFRONT_DOMAIN
CLOUDFRONT_KEY_PAIR_ID
CLOUDFRONT_PRIVATE_KEY          # PEM, base64-encoded
SENDGRID_API_KEY
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
STRIPE_PLATFORM_SHARE_PCT       # default: 20
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GITHUB_CLIENT_ID
GITHUB_CLIENT_SECRET
SENTRY_DSN
CELERY_BROKER_URL               # same as REDIS_URL
FLOWER_BASIC_AUTH               # user:password
```

---

## CI/CD Pipeline (GitHub Actions)

**Production-only deployment** (no staging environment).

```
on: any push (main, develop, feature branches)

jobs:
  quality:
    - flake8 (lint)
    - black --check (formatting)
    - mypy (type check)
    - pytest --cov (tests + coverage)

  build:
    needs: quality (success)
    - docker build lumio-app → ECR
    - docker build lumio-celery → ECR
    - docker build lumio-ffmpeg → ECR

  deploy:
    needs: build (success)
    environment: production (manual approval gate)
    - terraform init + plan + apply
    - ecs update-service (force new deployment)
    - wait for service stability
    - notify Slack
```

**Strategy:** All code goes directly to production after tests pass. Manual approval gate prevents accidental deployments. Fast iteration with safety.

---

## Current Phase

**Phase 0** — Starting now.
