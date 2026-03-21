"""Assessments models: quizzes, questions, attempts, and scoring"""

from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.courses.models import Lesson
from apps.enrollments.models import Enrollment, LessonProgress


class Quiz(models.Model):
    """Quiz associated with a lesson"""

    DIFFICULTY_EASY = "easy"
    DIFFICULTY_MEDIUM = "medium"
    DIFFICULTY_HARD = "hard"

    DIFFICULTY_CHOICES = [
        (DIFFICULTY_EASY, "Easy"),
        (DIFFICULTY_MEDIUM, "Medium"),
        (DIFFICULTY_HARD, "Hard"),
    ]

    lesson = models.OneToOneField(
        Lesson,
        on_delete=models.CASCADE,
        related_name="quiz",
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    # Quiz settings
    passing_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=70,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage score required to pass (0-100)",
    )
    time_limit_minutes = models.IntegerField(null=True, blank=True)
    shuffle_questions = models.BooleanField(default=True)
    show_answers_after_submission = models.BooleanField(default=True)
    allow_retake = models.BooleanField(default=True)
    max_attempts = models.IntegerField(null=True, blank=True)

    # Difficulty (for adaptive logic)
    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default=DIFFICULTY_MEDIUM,
    )
    adaptive_enabled = models.BooleanField(
        default=False,
        help_text="Enable adaptive difficulty based on performance",
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Quiz"
        verbose_name_plural = "Quizzes"
        ordering = ["lesson"]

    def __str__(self):
        return f"{self.lesson.title} - {self.title}"


class Question(models.Model):
    """Quiz question"""

    QUESTION_TYPE_MULTIPLE_CHOICE = "multiple_choice"
    QUESTION_TYPE_TRUE_FALSE = "true_false"
    QUESTION_TYPE_SHORT_ANSWER = "short_answer"
    QUESTION_TYPE_ESSAY = "essay"

    QUESTION_TYPES = [
        (QUESTION_TYPE_MULTIPLE_CHOICE, "Multiple Choice"),
        (QUESTION_TYPE_TRUE_FALSE, "True/False"),
        (QUESTION_TYPE_SHORT_ANSWER, "Short Answer"),
        (QUESTION_TYPE_ESSAY, "Essay"),
    ]

    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    question_type = models.CharField(
        max_length=50,
        choices=QUESTION_TYPES,
        default=QUESTION_TYPE_MULTIPLE_CHOICE,
    )
    text = models.TextField()
    explanation = models.TextField(
        blank=True,
        help_text="Explanation shown after submission",
    )

    # Points and difficulty
    points = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=1,
        validators=[MinValueValidator(0)],
    )
    difficulty = models.CharField(
        max_length=20,
        choices=Quiz.DIFFICULTY_CHOICES,
        default=Quiz.DIFFICULTY_MEDIUM,
    )

    # Concept tagging for adaptive quiz
    concept_tags = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True,
        help_text="Concept tags for adaptive question selection (e.g. ['algebra', 'fractions'])",
    )

    # Ordering
    order = models.PositiveIntegerField(default=0, db_index=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Question"
        verbose_name_plural = "Questions"
        unique_together = [("quiz", "order")]
        ordering = ["quiz", "order"]
        indexes = [
            models.Index(fields=["quiz", "order"]),
        ]

    def __str__(self):
        return f"Q{self.order}: {self.text[:50]}..."


class QuestionOption(models.Model):
    """Option for multiple choice or true/false questions"""

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
    )

    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0, db_index=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Question Option"
        verbose_name_plural = "Question Options"
        unique_together = [("question", "order")]
        ordering = ["question", "order"]

    def __str__(self):
        return f"{self.question.text[:30]}... → {self.text[:30]}..."


class QuizAttempt(models.Model):
    """Student's attempt at a quiz"""

    ATTEMPT_STATUS_IN_PROGRESS = "in_progress"
    ATTEMPT_STATUS_SUBMITTED = "submitted"
    ATTEMPT_STATUS_GRADED = "graded"

    ATTEMPT_STATUSES = [
        (ATTEMPT_STATUS_IN_PROGRESS, "In Progress"),
        (ATTEMPT_STATUS_SUBMITTED, "Submitted"),
        (ATTEMPT_STATUS_GRADED, "Graded"),
    ]

    lesson_progress = models.ForeignKey(
        LessonProgress,
        on_delete=models.CASCADE,
        related_name="attempt_records",
    )
    quiz = models.ForeignKey(
        Quiz,
        on_delete=models.CASCADE,
        related_name="attempts",
    )

    status = models.CharField(
        max_length=20,
        choices=ATTEMPT_STATUSES,
        default=ATTEMPT_STATUS_IN_PROGRESS,
        db_index=True,
    )

    # Timing
    started_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Scoring (calculated after submission)
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Points earned out of total possible points",
    )
    percentage_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Percentage score (0-100)",
    )
    is_passed = models.BooleanField(null=True, blank=True)

    # Attempt number (for tracking retakes)
    attempt_number = models.PositiveIntegerField(default=1)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Quiz Attempt"
        verbose_name_plural = "Quiz Attempts"
        unique_together = [("lesson_progress", "quiz", "attempt_number")]
        indexes = [
            models.Index(fields=["lesson_progress", "quiz"]),
            models.Index(fields=["status", "submitted_at"]),
        ]
        ordering = ["-started_at"]

    def __str__(self):
        return (
            f"Attempt {self.attempt_number} - {self.lesson_progress} - {self.get_status_display()}"
        )


class AttemptAnswer(models.Model):
    """Student's answer to a question in a quiz attempt"""

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="attempt_answers",
    )

    # Answer (depending on question type)
    selected_option = models.ForeignKey(
        QuestionOption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="student_answers",
        help_text="For multiple choice/true-false",
    )
    text_answer = models.TextField(
        blank=True,
        help_text="For short answer/essay",
    )

    # Scoring
    is_correct = models.BooleanField(null=True, blank=True)
    points_earned = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    # Manual grading (for essays/short answers)
    graded_by = models.CharField(
        max_length=255,
        blank=True,
        help_text="Instructor who graded this answer",
    )
    grading_notes = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Attempt Answer"
        verbose_name_plural = "Attempt Answers"
        unique_together = [("attempt", "question")]
        indexes = [
            models.Index(fields=["attempt", "is_correct"]),
        ]

    def __str__(self):
        return f"{self.attempt} → Q{self.question.order}"


class AttemptConceptScore(models.Model):
    """Per-concept score for a single quiz attempt."""

    attempt = models.ForeignKey(
        QuizAttempt,
        on_delete=models.CASCADE,
        related_name="concept_scores",
    )
    concept = models.CharField(max_length=100)
    score_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Score percentage for this concept in this attempt (0–100)",
    )

    class Meta:
        verbose_name = "Attempt Concept Score"
        verbose_name_plural = "Attempt Concept Scores"
        unique_together = [["attempt", "concept"]]

    def __str__(self):
        return f"{self.attempt} — {self.concept}: {self.score_pct}%"


class EnrollmentConceptProfile(models.Model):
    """Running-average concept performance for a student's enrollment."""

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name="concept_profiles",
    )
    concept = models.CharField(max_length=100, db_index=True)
    avg_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Running average score percentage for this concept (0–100)",
    )
    sample_count = models.PositiveIntegerField(
        default=1,
        help_text="Number of attempts factored into avg_score",
    )

    class Meta:
        verbose_name = "Enrollment Concept Profile"
        verbose_name_plural = "Enrollment Concept Profiles"
        unique_together = [["enrollment", "concept"]]
        indexes = [
            models.Index(fields=["enrollment", "avg_score"]),
        ]

    def __str__(self):
        return f"{self.enrollment} — {self.concept}: {self.avg_score}%"
