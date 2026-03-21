"""Search cache utilities"""

import hashlib
import json
from typing import Any, Optional
from django.core.cache import cache
from django.utils.text import slugify


class SearchCache:
    """Utility class for caching search results and popular searches"""

    SEARCH_RESULT_TTL = 300  # 5 minutes
    TRENDING_SEARCH_TTL = 1800  # 30 minutes
    FACET_TTL = 3600  # 1 hour

    @staticmethod
    def _get_search_key(query: str, filters: Optional[dict] = None) -> str:
        """Generate cache key for search results"""
        key_parts = [f"search:{slugify(query[:50])}"]

        if filters:
            # Sort filters for consistent key generation
            filter_str = json.dumps(filters, sort_keys=True, default=str)
            filter_hash = hashlib.md5(filter_str.encode()).hexdigest()[:8]
            key_parts.append(f"f:{filter_hash}")

        return ":".join(key_parts)

    @staticmethod
    def get_search_results(query: str, filters: Optional[dict] = None) -> Any:
        """Get cached search results"""
        key = SearchCache._get_search_key(query, filters)
        return cache.get(key)

    @staticmethod
    def set_search_results(query: str, results: list, filters: Optional[dict] = None) -> None:
        """Cache search results"""
        key = SearchCache._get_search_key(query, filters)
        cache.set(key, results, SearchCache.SEARCH_RESULT_TTL)

    @staticmethod
    def get_trending_searches(limit: int = 10) -> Any:
        """Get trending searches from cache"""
        key = f"search:trending:{limit}"
        return cache.get(key)

    @staticmethod
    def set_trending_searches(searches: list, limit: int = 10) -> None:
        """Cache trending searches"""
        key = f"search:trending:{limit}"
        cache.set(key, searches, SearchCache.TRENDING_SEARCH_TTL)

    @staticmethod
    def get_facets(content_type: Optional[str] = None) -> Any:
        """Get cached facet data"""
        if content_type:
            key = f"search:facets:{content_type}"
        else:
            key = "search:facets:all"
        return cache.get(key)

    @staticmethod
    def set_facets(facets: dict, content_type: Optional[str] = None) -> None:
        """Cache facet data"""
        if content_type:
            key = f"search:facets:{content_type}"
        else:
            key = "search:facets:all"
        cache.set(key, facets, SearchCache.FACET_TTL)

    @staticmethod
    def invalidate_search_cache() -> None:
        """Invalidate all search-related caches"""
        if hasattr(cache, "delete_pattern"):
            cache.delete_pattern("search:*")
        else:
            cache.clear()

    @staticmethod
    def get_course_analytics_cache(course_id: int) -> Any:
        """Get cached course analytics for search result enrichment"""
        key = f"search:analytics:course:{course_id}"
        return cache.get(key)

    @staticmethod
    def set_course_analytics_cache(course_id: int, analytics: dict) -> None:
        """Cache course analytics"""
        key = f"search:analytics:course:{course_id}"
        cache.set(key, analytics, SearchCache.FACET_TTL)
