# Adaptive Quiz Engine

## How It Works

On each quiz attempt, questions are reordered to prioritise topics the student has historically struggled with.

**Seed:** `hash(f"{enrollment_id}{attempt_number}") & 0x7FFFFFFF`
Same enrollment + attempt number always produces the same question order — deterministic and reproducible.

**Weight formula per question:**

```
tags = question.concept_tags          # e.g. ["algebra", "geometry"]
avg_score = mean score on those tags  # from EnrollmentConceptProfile
weight = clamp((100 - avg_score) / 30, 0.1, 3.0)
```

Questions with no tags get weight 1.0 (neutral). A student scoring 40% on "algebra" would see algebra questions weighted at ~2.0×.

## Concept Tracking

After each graded attempt:

1. `compute_concept_scores(attempt)` — groups answers by concept tag, computes `points_earned / points_possible` per concept.
2. `save_concept_scores(attempt, scores)` — bulk-creates `AttemptConceptScore` rows.
3. `update_concept_profile(enrollment, scores)` — upserts `EnrollmentConceptProfile` using a running average: `new_avg = (old_avg * n + new_score) / (n + 1)`.

## Weak Concept Surfacing

After a failed attempt the API returns the list of concepts where `avg_score < 70%`, allowing the frontend to suggest review materials before the next attempt.

## Models

| Model | Purpose |
|-------|---------|
| `Quiz` | Belongs to a Lesson; has `pass_threshold` (%) |
| `Question` | Has `question_type`, `concept_tags` (JSON array), `points` |
| `QuizAttempt` | Records each attempt: score, passed, started/submitted timestamps |
| `AttemptAnswer` | Per-question answer with `points_earned` |
| `AttemptConceptScore` | Per-concept score for one attempt |
| `EnrollmentConceptProfile` | Running average score per concept per enrollment |
