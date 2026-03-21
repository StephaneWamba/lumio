"""Adaptive quiz engine: seeded question selection and concept performance tracking."""

import random
from collections import defaultdict
from decimal import Decimal
from typing import List

import structlog

logger = structlog.get_logger(__name__)

WEAK_CONCEPT_THRESHOLD = 70.0  # avg_score below this is considered weak


def _seed(enrollment_id: int, attempt_number: int) -> int:
    """Deterministic seed: same enrollment + attempt → same question order."""
    return hash(f"{enrollment_id}{attempt_number}") & 0x7FFFFFFF


def select_questions(quiz, enrollment, attempt_number: int) -> list:
    """
    Return quiz questions in weighted order favouring weak concepts.

    Deterministic: same (enrollment_id, attempt_number) always produces
    the same sequence. Uses seeded RNG per spec:
        random.seed(hash(f"{enrollment_id}{attempt_number}"))

    Weight formula:
    - Questions covering concepts where the student's avg_score < 70% receive
      higher weight: weight = (100 - avg_score) / 30, clamped to [0.1, 3.0].
    - Questions with no concept tags receive weight 1.0 (neutral).
    """
    from .models import EnrollmentConceptProfile

    questions = list(quiz.questions.all())
    if not questions:
        return questions

    # Build weak-concept map: concept → avg_score
    weak_map: dict = {
        row["concept"]: float(row["avg_score"])
        for row in EnrollmentConceptProfile.objects.filter(
            enrollment=enrollment
        ).values("concept", "avg_score")
    }

    def _weight(question) -> float:
        tags = question.concept_tags or []
        if not tags:
            return 1.0
        scores = [weak_map.get(t, 70.0) for t in tags]
        avg = sum(scores) / len(scores)
        return max(0.1, min(3.0, (100.0 - avg) / 30.0))

    weights = [_weight(q) for q in questions]
    rng = random.Random(_seed(enrollment.id, attempt_number))

    # Weighted shuffle without replacement
    ordered: list = []
    remaining = list(zip(questions, weights))
    while remaining:
        total = sum(w for _, w in remaining)
        r = rng.uniform(0, total)
        cumulative = 0.0
        for i, (q, w) in enumerate(remaining):
            cumulative += w
            if r <= cumulative:
                ordered.append(q)
                remaining.pop(i)
                break

    logger.info(
        "adaptive_question_order",
        quiz_id=quiz.id,
        enrollment_id=enrollment.id,
        attempt_number=attempt_number,
        question_ids=[q.id for q in ordered],
    )
    return ordered


def compute_concept_scores(attempt) -> dict:
    """
    After quiz submission, compute per-concept score_pct from AttemptAnswer records.
    Returns {concept: Decimal(score_pct)} dict.
    """
    concept_correct: dict = defaultdict(Decimal)
    concept_total: dict = defaultdict(Decimal)

    for answer in attempt.answers.select_related("question").all():
        tags = answer.question.concept_tags or []
        if not tags:
            continue
        points_possible = answer.question.points
        points_earned = answer.points_earned or Decimal("0")
        for tag in tags:
            concept_total[tag] += points_possible
            concept_correct[tag] += points_earned

    result = {}
    for concept, total in concept_total.items():
        if total > 0:
            result[concept] = (concept_correct[concept] / total) * 100
    return result


def save_concept_scores(attempt, concept_scores: dict) -> None:
    """Persist AttemptConceptScore rows for this attempt."""
    from .models import AttemptConceptScore

    rows = [
        AttemptConceptScore(attempt=attempt, concept=concept, score_pct=score_pct)
        for concept, score_pct in concept_scores.items()
    ]
    AttemptConceptScore.objects.bulk_create(rows, ignore_conflicts=True)


def update_concept_profile(enrollment, concept_scores: dict) -> None:
    """
    Upsert EnrollmentConceptProfile records using a running average.
    Called after each graded attempt.
    """
    from .models import EnrollmentConceptProfile

    for concept, score_pct in concept_scores.items():
        profile, created = EnrollmentConceptProfile.objects.get_or_create(
            enrollment=enrollment,
            concept=concept,
            defaults={"avg_score": score_pct, "sample_count": 1},
        )
        if not created:
            new_count = profile.sample_count + 1
            profile.avg_score = (
                profile.avg_score * profile.sample_count + score_pct
            ) / new_count
            profile.sample_count = new_count
            profile.save(update_fields=["avg_score", "sample_count"])


def get_weak_concepts(enrollment, threshold: float = WEAK_CONCEPT_THRESHOLD) -> List[str]:
    """Return list of concepts where student's avg_score < threshold."""
    from .models import EnrollmentConceptProfile

    return list(
        EnrollmentConceptProfile.objects.filter(
            enrollment=enrollment,
            avg_score__lt=threshold,
        ).values_list("concept", flat=True)
    )
