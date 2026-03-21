"""Assessments serializers"""

from rest_framework import serializers
from decimal import Decimal
from .models import Quiz, Question, QuestionOption, QuizAttempt, AttemptAnswer


class QuestionOptionSerializer(serializers.ModelSerializer):
    """Question option serializer"""

    class Meta:
        model = QuestionOption
        fields = ["id", "text", "order"]
        read_only_fields = ["id"]

    def to_representation(self, instance):
        """Hide correct answer until quiz is graded"""
        data = super().to_representation(instance)
        request = self.context.get("request")

        # Only show is_correct if quiz is graded
        if request and hasattr(request, "quiz_attempt"):
            if request.quiz_attempt.status == QuizAttempt.ATTEMPT_STATUS_GRADED:
                data["is_correct"] = instance.is_correct

        return data


class QuestionSerializer(serializers.ModelSerializer):
    """Question with options"""

    options = QuestionOptionSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = [
            "id",
            "question_type",
            "text",
            "explanation",
            "points",
            "difficulty",
            "order",
            "options",
        ]
        read_only_fields = ["id"]


class QuizListSerializer(serializers.ModelSerializer):
    """Quiz list (minimal info)"""

    lesson_title = serializers.CharField(source="lesson.title", read_only=True)

    class Meta:
        model = Quiz
        fields = [
            "id",
            "lesson",
            "lesson_title",
            "title",
            "passing_score",
            "difficulty",
        ]
        read_only_fields = ["id"]


class QuizDetailSerializer(serializers.ModelSerializer):
    """Quiz with questions"""

    questions = QuestionSerializer(many=True, read_only=True)
    total_points = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = [
            "id",
            "lesson",
            "title",
            "description",
            "passing_score",
            "time_limit_minutes",
            "shuffle_questions",
            "show_answers_after_submission",
            "allow_retake",
            "max_attempts",
            "difficulty",
            "adaptive_enabled",
            "questions",
            "total_points",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_total_points(self, obj):
        """Calculate total points in quiz"""
        return obj.questions.aggregate(total=models.Sum("points"))["total"] or Decimal("0")


class AttemptAnswerSerializer(serializers.ModelSerializer):
    """Student answer to a question"""

    question_text = serializers.CharField(source="question.text", read_only=True)
    question_type = serializers.CharField(source="question.question_type", read_only=True)

    class Meta:
        model = AttemptAnswer
        fields = [
            "id",
            "question",
            "question_text",
            "question_type",
            "selected_option",
            "text_answer",
            "is_correct",
            "points_earned",
            "grading_notes",
        ]
        read_only_fields = [
            "id",
            "is_correct",
            "points_earned",
            "grading_notes",
        ]


class QuizAttemptListSerializer(serializers.ModelSerializer):
    """Quiz attempt list (summary)"""

    quiz_title = serializers.CharField(source="quiz.title", read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            "id",
            "quiz",
            "quiz_title",
            "attempt_number",
            "status",
            "percentage_score",
            "is_passed",
            "started_at",
            "submitted_at",
        ]
        read_only_fields = ["id"]


class QuizAttemptDetailSerializer(serializers.ModelSerializer):
    """Quiz attempt with answers"""

    answers = AttemptAnswerSerializer(many=True, read_only=True)
    quiz_title = serializers.CharField(source="quiz.title", read_only=True)

    class Meta:
        model = QuizAttempt
        fields = [
            "id",
            "quiz",
            "quiz_title",
            "status",
            "attempt_number",
            "started_at",
            "submitted_at",
            "score",
            "percentage_score",
            "is_passed",
            "answers",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class StartQuizAttemptSerializer(serializers.Serializer):
    """Request to start a quiz attempt"""

    quiz_id = serializers.IntegerField()


class SubmitQuizAttemptSerializer(serializers.Serializer):
    """Submit quiz attempt with answers"""

    answers = serializers.ListField(
        child=serializers.DictField(
            child=serializers.CharField(),
        ),
        help_text="List of {question_id, answer} objects",
    )
