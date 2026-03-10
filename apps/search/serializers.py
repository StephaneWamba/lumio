"""Search app serializers"""

from rest_framework import serializers
from .models import SearchIndex, SearchQuery


class SearchIndexSerializer(serializers.ModelSerializer):
    """Serializer for search results"""

    content_type_display = serializers.CharField(source="get_content_type_display", read_only=True)
    rating_display = serializers.SerializerMethodField()
    difficulty_display = serializers.SerializerMethodField()

    class Meta:
        model = SearchIndex
        fields = [
            "id",
            "content_type",
            "content_type_display",
            "object_id",
            "title",
            "description",
            "instructor_name",
            "category",
            "difficulty",
            "difficulty_display",
            "duration_hours",
            "rating",
            "rating_display",
            "review_count",
            "enrollment_count",
            "is_published",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_rating_display(self, obj):
        """Format rating with review count"""
        if obj.rating:
            return f"{obj.rating:.1f} ({obj.review_count} reviews)"
        return "No ratings yet"

    def get_difficulty_display(self, obj):
        """Display difficulty level"""
        if not obj.difficulty:
            return None
        return obj.difficulty.replace("_", " ").title()


class SearchQuerySerializer(serializers.ModelSerializer):
    """Serializer for search query tracking"""

    user_name = serializers.CharField(source="user.name", read_only=True)

    class Meta:
        model = SearchQuery
        fields = [
            "id",
            "query",
            "user_name",
            "result_count",
            "timestamp",
        ]
        read_only_fields = fields
