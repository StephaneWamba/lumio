"""Search app admin configuration"""
from django.contrib import admin
from .models import SearchIndex, SearchQuery


@admin.register(SearchIndex)
class SearchIndexAdmin(admin.ModelAdmin):
    """Admin for search index"""

    list_display = [
        "title",
        "content_type",
        "instructor_name",
        "category",
        "difficulty",
        "rating",
        "enrollment_count",
        "is_published",
        "updated_at",
    ]
    list_filter = ["content_type", "category", "difficulty", "is_published", "updated_at"]
    search_fields = ["title", "description", "instructor_name"]
    readonly_fields = [
        "search_vector",
        "created_at",
        "updated_at",
    ]
    fieldsets = (
        ("Content", {
            "fields": (
                "content_type",
                "object_id",
                "title",
                "description",
            )
        }),
        ("Metadata", {
            "fields": (
                "category",
                "difficulty",
                "duration_hours",
                "is_published",
            )
        }),
        ("Instructor & Ratings", {
            "fields": (
                "instructor_name",
                "rating",
                "review_count",
            )
        }),
        ("Engagement", {
            "fields": (
                "enrollment_count",
            )
        }),
        ("Search", {
            "fields": (
                "search_vector",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
    )


@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    """Admin for search query tracking"""

    list_display = [
        "query",
        "result_count",
        "user",
        "timestamp",
    ]
    list_filter = ["timestamp", "result_count"]
    search_fields = ["query", "user__email", "user__name"]
    readonly_fields = ["timestamp", "created_at"]
    fieldsets = (
        ("Query", {
            "fields": (
                "query",
                "result_count",
            )
        }),
        ("User", {
            "fields": (
                "user",
            )
        }),
        ("Metadata", {
            "fields": (
                "timestamp",
            )
        }),
    )

    def has_add_permission(self, request):
        """Disable manual creation in admin"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Only superusers can delete"""
        return request.user.is_superuser
