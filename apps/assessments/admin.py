"""Assessments app admin configuration"""
from django.contrib import admin
from .models import Quiz, Question, QuestionOption, QuizAttempt, AttemptAnswer


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    """Admin for quizzes"""

    list_display = ["lesson", "title", "passing_score", "difficulty", "created_at"]
    list_filter = ["difficulty", "adaptive_enabled", "allow_retake", "created_at"]
    search_fields = ["lesson__title", "title"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    """Admin for questions"""

    list_display = ["quiz", "order", "question_type", "points", "difficulty"]
    list_filter = ["question_type", "difficulty", "quiz"]
    search_fields = ["text", "quiz__title"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(QuestionOption)
class QuestionOptionAdmin(admin.ModelAdmin):
    """Admin for question options"""

    list_display = ["question", "text", "is_correct", "order"]
    list_filter = ["is_correct", "question__quiz"]
    search_fields = ["question__text", "text"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    """Admin for quiz attempts"""

    list_display = ["lesson_progress", "quiz", "attempt_number", "status", "percentage_score", "is_passed"]
    list_filter = ["status", "is_passed", "submitted_at"]
    search_fields = ["lesson_progress__enrollment__student__email", "quiz__title"]
    readonly_fields = ["started_at", "submitted_at", "created_at", "updated_at"]


@admin.register(AttemptAnswer)
class AttemptAnswerAdmin(admin.ModelAdmin):
    """Admin for attempt answers"""

    list_display = ["attempt", "question", "is_correct", "points_earned", "graded_at"]
    list_filter = ["is_correct", "graded_at", "attempt__quiz"]
    search_fields = ["attempt__lesson_progress__enrollment__student__email", "question__text"]
    readonly_fields = ["created_at", "updated_at"]
