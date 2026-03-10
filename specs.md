LMS — Complete Project Specification

Executive Summary
A modern learning platform where instructors create and sell courses, students learn through structured video content and quizzes, and the system handles everything behind the scenes — video processing, progress tracking, certificate generation, and automated email sequences. Think Teachable meets Canvas, but built from scratch with production-grade engineering.
What makes this portfolio-worthy isn't the concept (everyone understands an LMS) — it's the engineering underneath. A video upload triggers a multi-stage transcoding pipeline. A quiz submission feeds an adaptive engine. A course completion fires a PDF certificate generator. All of it asynchronous, all of it observable, all of it reliable.

System Domains
Domain 1 — Content Management
Instructors build courses through a structured hierarchy: a Course contains Sections, Sections contain Lessons, Lessons are either video, text, or quiz type. This sounds simple but the content tree has complex ordering, draft/published states at every level, and prerequisite logic between lessons. A student can't access Lesson 4 until they've completed Lesson 3 if the instructor configured it that way.
Domain 2 — Media Pipeline
The most technically impressive part of the system. An instructor uploads a raw video file. From that point, a fully automated pipeline takes over: the file lands in S3, a transcoding job picks it up, FFmpeg converts it to multiple quality levels (1080p, 720p, 480p), HLS streaming segments are generated, a thumbnail is extracted, and the final output is pushed to a CDN. The instructor's lesson goes from "processing" to "ready" with no manual intervention.
Domain 3 — Learning & Assessment
Students enroll in courses and work through content. The system tracks every interaction — video watch percentage, quiz attempts, lesson completions. A quiz isn't just right/wrong scoring. The adaptive engine tracks which concepts a student struggles with across attempts and can surface review material before letting them proceed. Progress is always calculated in real time from the event log, never stored as a stale counter.
Domain 4 — Cohorts & Enrollment
Courses can run in two modes. Self-paced means students enroll anytime and work at their own speed. Cohort-based means a fixed group starts together on a specific date, with scheduled content releases (drip publishing) and a shared discussion thread. Cohorts are used heavily in bootcamp-style or corporate training contexts and add significant scheduling complexity.
Domain 5 — Certificates & Credentials
When a student meets the completion criteria defined by the instructor, the system generates a certificate. This isn't just a static image — it's a dynamically rendered PDF with the student's name, course name, completion date, a unique verification ID, and the instructor's signature. The certificate lives at a public URL that anyone can visit to verify its authenticity.

User Roles & Permissions
Student — browses the course catalog, enrolls (free or paid), consumes content, takes quizzes, tracks their own progress, downloads certificates, leaves reviews.
Instructor — creates and manages courses, uploads videos, builds quizzes, sets pricing, views student analytics, manages cohort enrollment, sends announcements.
Admin — platform management, instructor approval, content moderation, revenue reporting, user management.
Corporate Manager — a special role for B2B use cases. Manages a team of learners, bulk-enrolls employees into courses, views team-wide completion reports.

Tech Stack
Backend

Runtime: Python with Django — mature, batteries-included, excellent ORM for the complex relational schema this project needs. Django admin also gives you a free internal tool for platform management
API layer: Django REST Framework with a clean versioned REST API. GraphQL considered but REST is more appropriate here given the predictable, resource-oriented data model
Architecture: Monolith with a clean app-per-domain structure (courses, enrollments, assessments, media, certificates, notifications). Django's app model maps perfectly to this

Databases

Primary DB: PostgreSQL — the content hierarchy, enrollment records, quiz attempts, and progress events all need strong relational integrity
Cache: Redis — used for session management, rate limiting, caching expensive progress calculations, and as the Celery broker
Search: PostgreSQL full-text search for the course catalog (sufficient at this scale, Elasticsearch is overkill until you have millions of courses)

Media & File Storage

AWS S3 — raw video uploads land here first, then processed outputs are stored in a separate bucket. Course thumbnails, instructor avatars, and certificate PDFs also live in S3
AWS CloudFront — CDN sitting in front of the processed video bucket. HLS segments are served from edge locations, making video playback fast globally regardless of where the student is
FFmpeg — the transcoding engine. Runs inside a worker container. Takes a raw upload and produces multiple quality renditions plus HLS playlist files

Background Jobs (Celery + Redis)
Every interesting thing in this system happens asynchronously:

Video transcoding pipeline (the most complex job — multi-stage with status updates at each step)
Certificate PDF generation on course completion
Email drip campaign scheduling and dispatch
Progress recalculation after lesson completion
Search index updates when course content changes
Cohort content release (drip publishing on schedule)
Enrollment confirmation and welcome email sequences

Authentication & Authorization

JWT with refresh rotation for API authentication
OAuth2 via Google and GitHub — critical for reducing signup friction in an EdTech context
Object-level permissions — a student can only access lessons in courses they're enrolled in. An instructor can only modify their own courses. Enforced at the queryset level, not just in views
Signed URLs for video content — students never get a direct S3 or CloudFront URL. Every video request goes through the API which validates enrollment, then issues a short-lived signed URL. Prevents content sharing outside the platform

Frontend

React with TypeScript — rich interactive UI requirements (video player, quiz engine, drag-and-drop course builder) make a SPA appropriate here
Video.js — open-source video player with HLS support, quality selector, playback speed control, and progress tracking hooks
TipTap — rich text editor for lesson content and course descriptions
React Query — server state management, particularly important for the real-time progress updates as students move through content
Tailwind CSS — utility-first styling, fast to build clean educational UI

Email

SendGrid or Resend — transactional emails (enrollment confirmation, certificate ready, cohort start reminder) and drip campaign delivery
Drip sequences are stored as scheduled Celery tasks, not a third-party marketing tool. This keeps the logic in-house and auditable

PDF Generation

WeasyPrint — Python library that renders HTML/CSS to PDF. Certificate templates are designed in HTML with dynamic variables, rendered server-side, stored in S3, and linked with a verification URL

Infrastructure

Docker — all services containerized: Django app, Celery workers, FFmpeg worker (separate container with heavier dependencies), Redis, PostgreSQL
Docker Compose — full local environment with one command
GitHub Actions — CI/CD pipeline: lint (flake8, black) → type check (mypy) → tests (pytest) → build Docker images → push → deploy
AWS ECS — container orchestration in production. The FFmpeg worker scales independently from the web workers based on queue depth
AWS RDS — managed PostgreSQL with automated backups
AWS ElastiCache — managed Redis

Observability

Structlog — structured JSON logging throughout Django and Celery workers
Celery Flower — real-time monitoring dashboard for the job queue. See which jobs are running, failed, retried
Sentry — error tracking with full Django and Celery integration
Prometheus + Grafana — dashboards for API response times, queue depth, transcoding job duration, active video streams


Core Features Breakdown
Course Builder
Instructors use a drag-and-drop interface to structure their course. Sections and lessons can be reordered freely. Each lesson has a type: video (triggers the upload pipeline), text (rich content editor), or quiz (quiz builder). Every lesson and section has its own draft/published state, so instructors can publish incrementally. Prerequisite gates can be set between lessons — completion required before proceeding.
Video Upload & Transcoding Pipeline
This is the centrepiece of the technical showcase. The instructor selects a video file in the course builder. The frontend requests a presigned S3 upload URL from the API, uploads directly to S3 (the Django server never touches the video bytes), then notifies the API that the upload is complete. The API creates a MediaAsset record with status "uploaded" and dispatches a transcoding job to Celery.
The Celery worker downloads the raw file, runs FFmpeg to produce 1080p, 720p, and 480p MP4 renditions, then runs a second FFmpeg pass to segment each rendition into HLS chunks and generate the playlist files. A thumbnail is extracted at the 10-second mark. All outputs are uploaded to the processed S3 bucket behind CloudFront. The MediaAsset status updates through "transcoding" → "packaging" → "ready". The instructor's UI polls the status and shows a progress indicator throughout.
If the job fails at any stage, Celery retries with exponential backoff. After three failures the job is moved to a dead letter queue and the instructor is notified to re-upload.
Adaptive Quiz Engine
Quizzes are built by instructors with multiple question types: multiple choice, true/false, short answer (manually graded), and code snippet (for technical courses). Each question is tagged with a concept. When a student takes a quiz, their per-concept performance is tracked across attempts, not just the overall score.
The adaptive element: if a student fails a quiz and retries, the engine serves more questions weighted toward concepts they scored poorly on in the previous attempt. It also surfaces a "Review these topics before retrying" block linking back to the relevant lessons. This is a significant step above a static quiz and demonstrates genuine product thinking.
Progress Tracking
Progress is event-sourced. Every meaningful student action — lesson opened, video watched past 80%, quiz submitted, lesson marked complete — is written as an immutable event. Progress percentages are derived from these events, not maintained as mutable counters. This means progress can never get out of sync, and it's trivially auditable. A background job periodically materializes progress summaries into a cache for fast dashboard rendering.
Cohort Enrollment & Drip Publishing
Instructors can create multiple cohorts for a course, each with a start date and a cap on enrollment. Content is released on a schedule relative to the cohort start date — Week 1 content unlocks on day 1, Week 2 content unlocks on day 7, and so on. Celery beat handles the scheduling. Students who enroll before the start date see a countdown. Students within a cohort share a discussion thread per lesson.
Certificate Generation
When a student meets the completion threshold (configurable per course — e.g., 100% of lessons complete plus a passing quiz score), a Celery job triggers certificate generation. WeasyPrint renders the HTML certificate template with the student's data, saves the PDF to S3, and creates a Certificate record with a UUID-based verification slug. The certificate is emailed to the student and appears in their profile. Anyone can visit /certificates/{slug} to see a public verification page confirming authenticity.
Email Drip Campaigns
Instructors define email sequences at the course level. "Send 1 day after enrollment: welcome email. Send 3 days after enrollment: tips for getting started. Send if no activity for 7 days: re-engagement email." These are stored as trigger rules. On enrollment, Celery schedules the applicable tasks using ETA (execute-at time). The re-engagement trigger is checked by a periodic task that scans for inactive enrollments. Instructors write email content in a simple template editor with dynamic variables.
Instructor Analytics
Instructors see a dashboard with: enrollment over time, completion rate per course, average quiz score per lesson (identifies which lessons are too hard), revenue breakdown, and student drop-off rate by lesson (shows exactly where students stop engaging). All computed from the event log using aggregation queries.
Course Marketplace
A public catalog where buyers browse courses by category, rating, price, and instructor. Course pages are server-rendered for SEO with full metadata. Ratings and reviews are collected after completion. Payments are handled via Stripe, with the platform taking a configurable revenue share and the remainder going to the instructor's connected Stripe account.

Key Engineering Challenges
Video pipeline reliability — raw uploads can be gigabytes. The pipeline has multiple failure points. The system needs idempotent job design, clear status tracking at each stage, retry logic, and dead letter handling. Demonstrating you've thought through failure at each step is what separates this from a tutorial project.
Signed video access — preventing students from sharing video URLs outside the platform requires every playback request to go through an authorization check and receive a short-lived signed CloudFront URL. This needs to be fast enough to not interrupt playback.
Progress calculation correctness — with event-sourced progress, you need to handle duplicate events (browser sends "video complete" twice), out-of-order events, and efficient materialization. Getting this right shows you understand the tradeoffs between event sourcing and mutable state.
Drip scheduling at scale — if 10,000 students enroll in a cohort simultaneously, you can't create 10,000 individual Celery tasks at enrollment time. The architecture needs a periodic scanner pattern rather than per-student scheduled tasks.
Quiz adaptive logic — the concept-weighted question selection needs to be deterministic for a given student state (retaking a quiz should give reproducible behaviour), fair across different question pools, and fast. This is a small algorithm design problem worth thinking through carefully.

What This Demonstrates to Reviewers

Async pipeline design — the video transcoding workflow is a textbook multi-stage background processing system with real failure scenarios
Event sourcing in practice — progress tracking from an immutable event log, not mutable counters
Media engineering — FFmpeg, HLS, CDN integration, signed URLs — most developers have never touched this stack
Content hierarchy modeling — courses, sections, lessons, prerequisites, cohorts, drip schedules — a genuinely complex domain model
Permissioning depth — object-level access control across five user roles is non-trivial
Product thinking — the adaptive quiz engine shows you think about the user experience, not just the technical requirements
