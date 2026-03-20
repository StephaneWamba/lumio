# Lumio Integration Tests

End-to-end integration tests that exercise the **live production API** at:

```
http://lumio-production-alb-1639211656.eu-central-1.elb.amazonaws.com
```

No mocks. No stubs. Every test makes real HTTP calls.

---

## Prerequisites

1. The production stack must be running (ECS Fargate services healthy).
2. Python 3.12 environment with dev dependencies installed:
   ```bash
   pip install -e ".[dev]"
   # or with uv:
   uv pip install -e ".[dev]"
   ```
3. `requests` is included in the main project dependencies — no extra install needed.

---

## Running the Tests

### All integration tests

```bash
pytest tests/integration/ -v -m integration --no-cov
```

The `--no-cov` flag is recommended for integration tests since they don't
measure application source coverage (they call the live API).

### A specific test file

```bash
pytest tests/integration/test_auth.py -v -m integration --no-cov
```

### A specific test

```bash
pytest tests/integration/test_health.py::test_health_check -v --no-cov
```

### Run with output on failure (show full response text)

```bash
pytest tests/integration/ -v -m integration --no-cov -s
```

---

## Test Isolation

Each test run generates a unique `TEST_RUN_ID` (`uuid4().hex[:8]`). All
test data (users, courses, cohorts) includes this ID in names/emails so
parallel or repeated runs never collide.

Example emails:
- `student_a3f72b1c@test.lumio.io`
- `instructor_a3f72b1c@test.lumio.io`

---

## Fixture Scoping

Session-scoped fixtures are used wherever possible to minimise round-trips:

| Fixture | Scope | What it does |
|---------|-------|--------------|
| `student_credentials` | session | Registers a student once |
| `instructor_credentials` | session | Registers an instructor once |
| `student_client` | session | Authenticated `AuthedClient` for the student |
| `instructor_client` | session | Authenticated `AuthedClient` for the instructor |
| `published_course` | session | Creates course + section + lesson, publishes it |
| `student_enrollment` | session | Enrolls the student in the published course |

---

## Test Files

| File | What it tests |
|------|--------------|
| `test_health.py` | `/health/`, `/api/schema/`, `/api/docs/` |
| `test_auth.py` | Registration, login, token refresh, profile, password change |
| `test_courses.py` | Course/section/lesson CRUD, publish/unpublish |
| `test_enrollments.py` | Enroll, list enrollments, progress events |
| `test_assessments.py` | Quiz list/detail, attempt start/submit, adaptive retry |
| `test_search.py` | FTS search, filters, facets, trending, suggestions |
| `test_media.py` | Video upload initiation, signed URL endpoints |
| `test_payments.py` | Prices, payment initiation, invoices, Stripe onboarding |
| `test_analytics.py` | Course/lesson/quiz analytics, engagement metrics |
| `test_certificates.py` | Earned certs, templates, awards, verification |
| `test_cohorts.py` | Cohort CRUD, join, drip schedules, release |
| `test_notifications.py` | Notification inbox, templates, preferences, logs |

---

## Notes

- Tests **do not clean up** created data automatically. The production DB will
  accumulate test users/courses from each run (scoped to their `TEST_RUN_ID`).
  Periodic manual cleanup or a scheduled database purge of `@test.lumio.io`
  emails is recommended.

- Tests marked with `pytest.skip()` indicate a prerequisite that could not be
  met (e.g. Phase 3 endpoints returning 501). These are not failures.

- The `--no-cov` flag prevents pytest-cov from trying to instrument the live
  API server (which is not possible and would error).
