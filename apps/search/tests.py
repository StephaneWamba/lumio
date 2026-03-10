"""Search app tests"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APITestCase, APIClient
from rest_framework import status

from apps.courses.models import Course
from apps.users.models import User
from .models import SearchIndex, SearchQuery
from .cache import SearchCache

User = get_user_model()


class SearchIndexModelTests(TestCase):
    """Tests for SearchIndex model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="instructor@test.com",
            password="testpass123",
            name="Test Instructor",
            role="instructor",
        )
        self.course = Course.objects.create(
            title="Django Fundamentals",
            description="Learn Django basics",
            instructor=self.user,
            status="draft",
        )

    def test_create_search_index(self):
        """Test creating a search index entry"""
        index = SearchIndex.objects.create(
            content_type="course",
            object_id=self.course.id,
            title="Django Fundamentals",
            description="Learn Django basics",
            instructor_name="Test Instructor",
            category="Web Development",
            difficulty="beginner",
            duration_hours=10.5,
            rating=4.5,
            review_count=120,
            enrollment_count=500,
            is_published=True,
        )
        self.assertEqual(index.title, "Django Fundamentals")
        self.assertEqual(index.content_type, "course")
        self.assertEqual(index.rating, 4.5)

    def test_unique_content_constraint(self):
        """Test unique constraint on content_type + object_id"""
        SearchIndex.objects.create(
            content_type="course",
            object_id=1,
            title="Course 1",
            description="Test",
            is_published=True,
        )
        with self.assertRaises(Exception):
            SearchIndex.objects.create(
                content_type="course",
                object_id=1,
                title="Course 1 Duplicate",
                description="Test",
                is_published=True,
            )

    def test_search_index_str(self):
        """Test string representation"""
        index = SearchIndex.objects.create(
            content_type="course",
            object_id=1,
            title="Test Course",
            description="Test",
            is_published=True,
        )
        self.assertEqual(str(index), "Course: Test Course")


class SearchQueryModelTests(TestCase):
    """Tests for SearchQuery model"""

    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            email="student@test.com",
            password="testpass123",
            name="Test Student",
        )

    def test_create_search_query(self):
        """Test creating a search query record"""
        query = SearchQuery.objects.create(
            query="django tutorial",
            user=self.user,
            result_count=42,
        )
        self.assertEqual(query.query, "django tutorial")
        self.assertEqual(query.result_count, 42)
        self.assertIsNotNone(query.timestamp)

    def test_search_query_anonymous(self):
        """Test creating a search query without user"""
        query = SearchQuery.objects.create(
            query="python learning",
            result_count=100,
        )
        self.assertIsNone(query.user)
        self.assertEqual(query.result_count, 100)

    def test_search_query_str(self):
        """Test string representation"""
        query = SearchQuery.objects.create(
            query="test search",
            result_count=5,
        )
        self.assertEqual(str(query), '"test search" (5 results)')


class SearchCacheTests(TestCase):
    """Tests for search cache utility"""

    def setUp(self):
        """Clear cache before each test"""
        SearchCache.invalidate_search_cache()

    def tearDown(self):
        """Clear cache after each test"""
        SearchCache.invalidate_search_cache()

    def test_search_result_caching(self):
        """Test caching search results"""
        query = "django"
        results = [
            {"id": 1, "title": "Django Basics"},
            {"id": 2, "title": "Django Advanced"},
        ]

        # First call should not be cached
        self.assertIsNone(SearchCache.get_search_results(query))

        # Set cache
        SearchCache.set_search_results(query, results)

        # Second call should hit cache
        cached = SearchCache.get_search_results(query)
        self.assertEqual(cached, results)

    def test_search_cache_with_filters(self):
        """Test caching with filters"""
        query = "python"
        filters = {"difficulty": "beginner", "category": "web"}
        results = [{"id": 1, "title": "Python Basics"}]

        SearchCache.set_search_results(query, results, filters)
        cached = SearchCache.get_search_results(query, filters)

        self.assertEqual(cached, results)

    def test_facets_caching(self):
        """Test facet caching"""
        facets = {
            "categories": ["Web Development", "Mobile"],
            "difficulties": ["Beginner", "Advanced"],
        }

        # Not cached initially
        self.assertIsNone(SearchCache.get_facets("course"))

        # Set cache
        SearchCache.set_facets(facets, "course")

        # Should be cached now
        cached = SearchCache.get_facets("course")
        self.assertEqual(cached, facets)

    def test_trending_searches_cache(self):
        """Test trending searches cache"""
        trending = [
            {"query": "django", "count": 100},
            {"query": "python", "count": 80},
        ]

        SearchCache.set_trending_searches(trending, limit=10)
        cached = SearchCache.get_trending_searches(limit=10)

        self.assertEqual(cached, trending)


class SearchAPITests(APITestCase):
    """Tests for search API endpoints"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="instructor@test.com",
            password="testpass123",
            name="Test Instructor",
            role="instructor",
        )

        # Create search index entries
        for i in range(5):
            SearchIndex.objects.create(
                content_type="course",
                object_id=i + 1,
                title=f"Course {i + 1}",
                description=f"Description for course {i + 1}",
                instructor_name="Test Instructor",
                category="Web Development" if i % 2 == 0 else "Mobile",
                difficulty="beginner" if i % 3 == 0 else "intermediate",
                duration_hours=10 + i,
                rating=4.0 + (i * 0.1),
                review_count=100 + (i * 10),
                enrollment_count=500 + (i * 50),
                is_published=True,
            )

    def test_search_list(self):
        """Test listing search results"""
        response = self.client.get("/api/search/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 5)

    def test_search_with_query_param(self):
        """Test searching with query parameter"""
        response = self.client.get("/api/search/?q=Course")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_filter_by_category(self):
        """Test filtering by category"""
        response = self.client.get("/api/search/?category=Web%20Development")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_filter_by_difficulty(self):
        """Test filtering by difficulty"""
        response = self.client.get("/api/search/?difficulty=beginner")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_facets_endpoint(self):
        """Test facets endpoint"""
        response = self.client.get("/api/search/facets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("categories", response.data)
        self.assertIn("difficulties", response.data)
        self.assertIn("instructors", response.data)

    def test_search_facets_by_content_type(self):
        """Test facets for specific content type"""
        response = self.client.get("/api/search/facets/?content_type=course")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_trending_endpoint(self):
        """Test trending searches endpoint"""
        # Create some search queries
        for i in range(3):
            SearchQuery.objects.create(
                query="django",
                result_count=100,
            )
        for i in range(2):
            SearchQuery.objects.create(
                query="python",
                result_count=80,
            )

        response = self.client.get("/api/search/trending/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)

    def test_search_suggestions_endpoint(self):
        """Test suggestions endpoint"""
        response = self.client.get("/api/search/suggestions/?q=Cour")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_search_suggestions_min_length(self):
        """Test suggestions with short query"""
        response = self.client.get("/api/search/suggestions/?q=a")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_search_query_tracking(self):
        """Test that search queries are tracked"""
        initial_count = SearchQuery.objects.count()
        self.client.get("/api/search/?q=django")
        final_count = SearchQuery.objects.count()
        self.assertGreater(final_count, initial_count)

    def test_search_pagination(self):
        """Test search result pagination"""
        response = self.client.get("/api/search/?page=1")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_search_ordering(self):
        """Test search result ordering"""
        response = self.client.get("/api/search/?ordering=-rating")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unpublished_content_not_searchable(self):
        """Test that unpublished content is not returned"""
        SearchIndex.objects.create(
            content_type="course",
            object_id=99,
            title="Unpublished Course",
            description="Should not appear",
            is_published=False,
        )
        response = self.client.get("/api/search/?q=Unpublished")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should not return unpublished content
        for result in response.data.get("results", []):
            self.assertTrue(result["is_published"])


class SearchQueryAnalyticsTests(APITestCase):
    """Tests for search query analytics"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.admin_user = User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
            name="Admin",
        )
        self.normal_user = User.objects.create_user(
            email="user@test.com",
            password="testpass123",
            name="Normal User",
        )

    def test_search_queries_admin_access(self):
        """Test admin can access search queries"""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/search/queries/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_search_queries_normal_user_denied(self):
        """Test normal users cannot access search queries"""
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get("/api/search/queries/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_search_analytics_endpoint(self):
        """Test search analytics endpoint"""
        # Create sample searches
        for i in range(5):
            SearchQuery.objects.create(
                query=f"query{i}",
                result_count=i * 10,
            )

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get("/api/search/queries/analytics/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("total_searches", response.data)
        self.assertIn("unique_queries", response.data)

    def test_search_analytics_requires_admin(self):
        """Test analytics endpoint requires admin"""
        self.client.force_authenticate(user=self.normal_user)
        response = self.client.get("/api/search/queries/analytics/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
