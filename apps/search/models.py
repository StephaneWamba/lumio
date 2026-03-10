"""Search app models"""

from django.db import models
from django.contrib.postgres.search import SearchVectorField
from apps.courses.models import Course, Lesson, Section
from apps.users.models import User


class SearchIndex(models.Model):
    """Denormalized search index for fast full-text search"""

    # Type of indexed content
    CONTENT_TYPES = [
        ("course", "Course"),
        ("lesson", "Lesson"),
        ("instructor", "Instructor"),
    ]

    content_type = models.CharField(max_length=20, choices=CONTENT_TYPES)
    object_id = models.PositiveIntegerField()  # ID of the indexed object

    # Denormalized searchable fields
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    instructor_name = models.CharField(max_length=255, blank=True, db_index=True)
    category = models.CharField(max_length=100, blank=True, db_index=True)
    difficulty = models.CharField(max_length=20, blank=True, db_index=True)
    duration_hours = models.FloatField(null=True, blank=True)
    rating = models.FloatField(null=True, blank=True)
    review_count = models.PositiveIntegerField(default=0)
    enrollment_count = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=True, db_index=True)

    # Full-text search vector
    search_vector = SearchVectorField(null=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["content_type", "is_published"]),
            models.Index(fields=["category", "is_published"]),
            models.Index(fields=["-rating", "review_count"]),
            models.Index(fields=["-created_at"]),
        ]
        unique_together = [("content_type", "object_id")]
        verbose_name_plural = "Search Indexes"

    def __str__(self):
        return f"{self.get_content_type_display()}: {self.title}"


class SearchQuery(models.Model):
    """Track search queries for analytics and trending searches"""

    query = models.CharField(max_length=255, db_index=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    result_count = models.PositiveIntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["query", "-timestamp"]),
        ]
        verbose_name_plural = "Search Queries"

    def __str__(self):
        return f'"{self.query}" ({self.result_count} results)'
