# Architecture

## Services

Four ECS Fargate services, each with a dedicated Docker image:

| Service | Image | Role | Queues |
|---------|-------|------|--------|
| `lumio-app` | `lumio-app` | Django API (Gunicorn, 3 replicas) | — |
| `lumio-celery` | `lumio-celery` | Celery worker | `default`, `email`, `certificates` |
| `lumio-beat` | `lumio-celery` | Celery Beat scheduler | — |
| `lumio-ffmpeg` | `lumio-ffmpeg` | Video transcoding worker | `transcoding` |

The FFmpeg worker is isolated on its own queue so API workers never compete with CPU-heavy transcoding jobs.

## Data Stores

- **PostgreSQL 16 (RDS)** — primary store for all domain models
- **Redis 7 (ElastiCache)** — Celery broker, task result backend, analytics cache (1h TTL), CloudFront URL cache (5min TTL), auth token store

## Media Flow

1. Client requests a presigned PUT URL from the API.
2. Client uploads raw video directly to S3 (`lumio-raw-uploads`) — Django never proxies bytes.
3. API enqueues `transcode_video` on the `transcoding` queue.
4. FFmpeg worker streams the file in 8MB chunks, runs FFmpeg to produce HLS at 1080p/720p/480p, uploads segments + playlists to S3 (`lumio-processed-media`).
5. Playback URLs are signed CloudFront URLs with a 5-minute TTL, generated on demand and cached in Redis. Students never receive raw S3 URLs.

## Scheduled Jobs (Celery Beat)

| Task | Schedule | Purpose |
|------|----------|---------|
| `scan_and_release_drip` | Hourly | Bulk-unlock cohort lessons where `start_date + unlock_day ≤ now` |
| `check_course_completions` | Every 15 min | Detect completed enrollments, trigger certificate generation |
| `scan_reengagement` | Daily | Find inactive students, send re-engagement emails |
| `cleanup_expired_tokens` | Daily | Purge stale Redis auth tokens |

## Design Decisions

**Event-sourced progress** — `ProgressEvent` rows are append-only. Progress is derived from the log, not a mutable counter. Handles duplicates and out-of-order events cleanly.

**Periodic drip scanner** — One hourly task bulk-creates `LessonUnlock` records for all eligible cohorts. Scales flat regardless of enrollment size — no per-student tasks.

**Deterministic adaptive quiz** — RNG seeded with `hash(enrollment_id + attempt_number)`. Same enrollment state always produces the same question order.

**PostgreSQL FTS over Elasticsearch** — `tsvector` column with GIN index covers full-text course search. Eliminates an infrastructure component with no meaningful trade-off below ~100k courses.
