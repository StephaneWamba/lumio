"""Search app custom filters"""
from django_filters import rest_framework as filters
from django.contrib.postgres.search import SearchQuery, SearchRank
from .models import SearchIndex


class SearchFilterSet(filters.FilterSet):
    """Faceted filtering for search results"""

    # Search query field
    q = filters.CharFilter(
        field_name="search_vector",
        method="filter_search_vector",
        label="Search query",
    )

    # Facet filters
    content_type = filters.ChoiceFilter(
        choices=SearchIndex.CONTENT_TYPES,
        label="Content type",
    )

    category = filters.CharFilter(
        field_name="category",
        lookup_expr="icontains",
        label="Category",
    )

    difficulty = filters.ChoiceFilter(
        choices=[
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
            ("expert", "Expert"),
        ],
        label="Difficulty",
    )

    instructor = filters.CharFilter(
        field_name="instructor_name",
        lookup_expr="icontains",
        label="Instructor",
    )

    rating_min = filters.NumberFilter(
        field_name="rating",
        lookup_expr="gte",
        label="Minimum rating",
    )

    duration_max = filters.NumberFilter(
        field_name="duration_hours",
        lookup_expr="lte",
        label="Maximum duration (hours)",
    )

    is_published = filters.BooleanFilter(
        field_name="is_published",
        label="Published only",
        initial=True,
    )

    ordering = filters.OrderingFilter(
        fields={
            "rating": "rating",
            "review_count": "review_count",
            "enrollment_count": "enrollment_count",
            "created_at": "created_at",
            "updated_at": "updated_at",
            "title": "title",
        },
        label="Sort by",
    )

    class Meta:
        model = SearchIndex
        fields = [
            "q",
            "content_type",
            "category",
            "difficulty",
            "instructor",
            "rating_min",
            "duration_max",
            "is_published",
        ]

    def filter_search_vector(self, queryset, name, value):
        """Filter by full-text search on search_vector"""
        if not value:
            return queryset

        search_query = SearchQuery(value, search_type="websearch")
        return (
            queryset.filter(search_vector=search_query)
            .annotate(rank=SearchRank("search_vector", search_query))
            .order_by("-rank")
        )
