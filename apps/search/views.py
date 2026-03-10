"""Search app views"""

from rest_framework import viewsets, status, filters as drf_filters
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

from .models import SearchIndex, SearchQuery
from .serializers import SearchIndexSerializer, SearchQuerySerializer
from .filters import SearchFilterSet
from .cache import SearchCache


class SearchViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for searching courses and instructors"""

    permission_classes = [AllowAny]
    serializer_class = SearchIndexSerializer
    filterset_class = SearchFilterSet
    filter_backends = [drf_filters.OrderingFilter]

    def get_queryset(self):
        """Get published search results, filtered by user permissions"""
        return SearchIndex.objects.filter(is_published=True).select_related()

    def list(self, request, *args, **kwargs):
        """List search results with caching"""
        # Get search query from params
        search_query = request.query_params.get("q", "").strip()
        filters_dict = {
            "content_type": request.query_params.get("content_type"),
            "category": request.query_params.get("category"),
            "difficulty": request.query_params.get("difficulty"),
            "instructor": request.query_params.get("instructor"),
            "rating_min": request.query_params.get("rating_min"),
            "duration_max": request.query_params.get("duration_max"),
        }
        # Remove None values from filters
        filters_dict = {k: v for k, v in filters_dict.items() if v}

        # Try to get from cache
        if search_query:
            cached_results = SearchCache.get_search_results(search_query, filters_dict)
            if cached_results is not None:
                return Response(cached_results)

        # Track search query
        if search_query:
            SearchQuery.objects.create(
                query=search_query,
                user=request.user if request.user.is_authenticated else None,
                result_count=0,  # Will update after filter
            )

        # Perform search
        response = super().list(request, *args, **kwargs)

        # Cache results if search query provided
        if search_query and response.status_code == 200:
            result_count = (
                response.data.get("count", 0)
                if isinstance(response.data, dict)
                else len(response.data)
            )
            SearchCache.set_search_results(search_query, response.data, filters_dict)

            # Update result count in database
            latest = SearchQuery.objects.filter(query=search_query).latest("timestamp")
            latest.result_count = result_count
            latest.save()

        return response

    @action(detail=False, methods=["get"])
    def facets(self, request):
        """Get available facet options for filtering"""
        content_type = request.query_params.get("content_type")

        # Try to get from cache
        cached_facets = SearchCache.get_facets(content_type)
        if cached_facets:
            return Response(cached_facets)

        # Build facets
        queryset = self.get_queryset()
        if content_type:
            queryset = queryset.filter(content_type=content_type)

        facets = {
            "content_types": [{"value": ct[0], "label": ct[1]} for ct in SearchIndex.CONTENT_TYPES],
            "categories": list(
                queryset.values_list("category", flat=True)
                .distinct()
                .filter(category__isnull=False)
                .order_by("category")
            ),
            "difficulties": [
                {"value": "beginner", "label": "Beginner"},
                {"value": "intermediate", "label": "Intermediate"},
                {"value": "advanced", "label": "Advanced"},
                {"value": "expert", "label": "Expert"},
            ],
            "instructors": list(
                queryset.values_list("instructor_name", flat=True)
                .distinct()
                .filter(instructor_name__isnull=False)
                .order_by("instructor_name")
            ),
            "rating_range": {
                "min": 0,
                "max": 5,
                "step": 0.5,
            },
            "duration_range": {
                "min": 0,
                "max": int(queryset.aggregate(Avg("duration_hours"))["duration_hours__avg"] or 0)
                + 10,
                "step": 5,
            },
        }

        # Cache facets
        SearchCache.set_facets(facets, content_type)

        return Response(facets)

    @action(detail=False, methods=["get"])
    def trending(self, request):
        """Get trending searches"""
        limit = int(request.query_params.get("limit", 10))

        # Try to get from cache
        cached_trending = SearchCache.get_trending_searches(limit)
        if cached_trending:
            return Response(cached_trending)

        # Get trending searches from last 7 days
        seven_days_ago = timezone.now() - timedelta(days=7)
        trending = (
            SearchQuery.objects.filter(
                timestamp__gte=seven_days_ago,
                result_count__gt=0,
            )
            .values("query")
            .annotate(
                count=Count("id"),
            )
            .order_by("-count")[:limit]
        )

        result = [{"query": t["query"], "count": t["count"]} for t in trending]

        # Cache trending
        SearchCache.set_trending_searches(result, limit)

        return Response(result)

    @action(detail=False, methods=["get"])
    def suggestions(self, request):
        """Get search suggestions based on partial query"""
        q = request.query_params.get("q", "").strip()
        limit = int(request.query_params.get("limit", 5))

        if not q or len(q) < 2:
            return Response([])

        # Get matching titles from search index
        suggestions = (
            SearchIndex.objects.filter(
                Q(title__icontains=q) | Q(description__icontains=q),
                is_published=True,
            )
            .values_list("title", flat=True)
            .distinct()
            .order_by("title")[:limit]
        )

        return Response(list(suggestions))


class SearchQueryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for browsing search query analytics (admin only)"""

    queryset = SearchQuery.objects.all()
    serializer_class = SearchQuerySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["query", "timestamp"]
    ordering_fields = ["timestamp", "result_count"]
    ordering = ["-timestamp"]

    def get_queryset(self):
        """Only admins can see all searches"""
        if self.request.user.is_staff or self.request.user.role == "admin":
            return SearchQuery.objects.all()
        raise PermissionDenied("Admin access required")

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        """Get search analytics"""
        if not (request.user.is_staff or request.user.role == "admin"):
            return Response(
                {"detail": "Admin access required"},
                status=status.HTTP_403_FORBIDDEN,
            )

        period_days = int(request.query_params.get("days", 30))
        start_date = timezone.now() - timedelta(days=period_days)

        analytics = {
            "total_searches": SearchQuery.objects.filter(timestamp__gte=start_date).count(),
            "unique_queries": SearchQuery.objects.filter(timestamp__gte=start_date)
            .values("query")
            .distinct()
            .count(),
            "avg_results_per_query": SearchQuery.objects.filter(
                timestamp__gte=start_date
            ).aggregate(Avg("result_count"))["result_count__avg"]
            or 0,
            "zero_result_queries": SearchQuery.objects.filter(
                timestamp__gte=start_date,
                result_count=0,
            ).count(),
        }

        return Response(analytics)
