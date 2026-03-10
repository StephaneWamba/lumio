# Lumio LMS — Production-Grade Learning Management System

A comprehensive, production-grade LMS where instructors create and sell courses, students learn through structured content with video, quizzes, and certificates. Built with Django, Celery, AWS, and React.

**Status:** Phase 0 Foundation (Infrastructure & CI/CD scaffolded)

---

## Quick Start (Local Development)

### Prerequisites
- Docker & Docker Compose
- Python 3.12 (optional, for non-Docker development)
- Git

### Setup

```bash
# Clone repository
git clone <repo-url> && cd lumio

# Copy environment file
cp .env.example .env.local

# Start all services (PostgreSQL, Redis, Django, Celery, Celery Beat)
docker-compose up -d

# Run migrations
docker-compose exec django python manage.py migrate

# Create superuser
docker-compose exec django python manage.py createsuperuser

# Access the app
# API: http://localhost:8000
# Admin: http://localhost:8000/admin
# Docs: http://localhost:8000/api/docs/
# Health check: http://localhost:8000/health/
```

### Stopping Services

```bash
docker-compose down
```

---

## Architecture Overview

### Backend Stack
- **Framework:** Django 5.x + Django REST Framework
- **Database:** PostgreSQL 16 (AWS RDS in production)
- **Cache & Jobs:** Redis 7 + Celery 5
- **Auth:** JWT + OAuth2 (Google, GitHub)
- **Media:** AWS S3 + CloudFront + FFmpeg
- **Email:** Resend
- **PDF:** WeasyPrint
- **Monitoring:** Structlog + Sentry + Prometheus + Grafana
- **Infrastructure:** AWS ECS Fargate + Terraform
- **CI/CD:** GitHub Actions

### Apps (Domain-Driven)
- `apps/users/` — Custom user model, auth, profiles
- `apps/courses/` — Course hierarchy (Course → Section → Lesson)
- `apps/media/` — Video upload, transcoding pipeline
- `apps/enrollments/` — Enrollment, event-sourced progress
- `apps/assessments/` — Quizzes, adaptive engine
- `apps/cohorts/` — Cohort management, drip publishing
- `apps/certificates/` — Certificate generation & verification
- `apps/notifications/` — Email drip campaigns
- `apps/payments/` — Stripe Connect, marketplace

---

## Development

### Running Tests

```bash
docker-compose exec django pytest --cov=apps -v
```

### Linting & Formatting

```bash
docker-compose exec django flake8 apps config
docker-compose exec django black apps config
docker-compose exec django mypy apps config --ignore-missing-imports
```

### Django Admin

```
http://localhost:8000/admin
```

### Celery Monitoring (Flower)

```bash
# Access in development via logs
docker-compose logs celery
```

### API Documentation

```
http://localhost:8000/api/docs/
```

---

## Production Deployment

### Prerequisites
- AWS Account
- GitHub repository
- Terraform (v1.7+)
- AWS CLI

### Setup

1. **Configure AWS credentials:**
   ```bash
   aws configure
   ```

2. **Set GitHub Secrets:**
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_ACCOUNT_ID`
   - `TF_STATE_BUCKET` (S3 bucket for Terraform state)
   - `SLACK_WEBHOOK` (optional, for notifications)

3. **Terraform State Backend:**
   ```bash
   # Create S3 bucket for Terraform state
   aws s3 mb s3://lumio-tfstate-$(date +%s) --region us-east-1

   # Create DynamoDB table for locking
   aws dynamodb create-table \
     --table-name lumio-tflock \
     --attribute-definitions AttributeName=LockID,AttributeType=S \
     --key-schema AttributeName=LockID,KeyType=HASH \
     --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
     --region us-east-1
   ```

4. **Deploy:**
   - Push code to main branch
   - GitHub Actions will run tests, build Docker images, and deploy
   - Manual approval required before production deployment

---

## Roadmap

| Phase | Description |
|-------|-------------|
| **0** | Infrastructure & CI/CD Foundation ✓ |
| **1** | Identity, Auth & Permissions |
| **2** | Content Management (Course Builder) |
| **3** | Media Pipeline (Video Transcoding) |
| **4** | Enrollment & Event-Sourced Progress |
| **5** | Assessment (Adaptive Quiz Engine) |
| **6** | Cohorts & Drip Publishing |
| **7** | Certificate Generation |
| **8** | Email Drip Campaigns |
| **9** | Payments & Marketplace |
| **10** | Instructor Analytics |
| **11** | Observability & Security Hardening |
| **12** | Frontend (React) |

---

## Key Design Decisions

- **Event-Sourced Progress:** Student progress derived from immutable event log, never mutable counters
- **Periodic Scanner for Drip:** Content unlock via hourly scanner, not per-student tasks (scales to 10k+ students)
- **Deterministic Adaptive Quiz:** RNG seeded by `hash(enrollment_id + attempt_number)` for reproducibility
- **Separate FFmpeg Worker:** Dedicated ECS task for transcoding, scales independently
- **Signed Video URLs:** Students never receive raw S3/CloudFront URLs; all playback via API
- **Production-Only Deployment:** Direct to production with manual approval gate; no staging environment

---

## Documentation

- `CLAUDE.md` — Development guidelines, conventions, constraints
- `specs.md` — Complete feature specification
- Terraform — Infrastructure as Code documentation in `terraform/`

---

## Support

For issues, refer to `CLAUDE.md` or the project specifications.

---

**Built with ❤️ for production**
