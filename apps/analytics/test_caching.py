"""
Tests for analytics Redis caching (1h TTL).

Verifies:
  - retrieve() caches the response in Redis on first call
  - retrieve() returns cached data on second call (no DB hit needed)
  - recalculate() invalidates the cache so next retrieve() reflects fresh data
"""

import uuid
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.courses.models import Course
from apps.enrollments.models import Enrollment
from apps.users.models import User
from .models import CourseAnalytics


def _user(role=User.ROLE_INSTRUCTOR, prefix="user"):
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"{prefix}+{uid}@analytics-cache-test.lumio",
        name=f"User {uid}",
        password="pass",
        role=role,
    )


class AnalyticsCacheTests(TestCase):
    """CourseAnalytics retrieve endpoint uses Redis cache with 1h TTL."""

    def setUp(self):
        self.client = APIClient()
        self.instructor = _user(User.ROLE_INSTRUCTOR, "instructor")
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Cache Test Course",
            is_published=True,
        )
        self.analytics = CourseAnalytics.objects.create(
            course=self.course,
            total_enrollments=5,
            active_students=3,
            completed_students=1,
        )
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_retrieve_populates_cache(self):
        """First retrieve() stores data in cache."""
        self.client.force_authenticate(user=self.instructor)
        self.client.get(reverse("course-analytics-detail", args=[self.analytics.id]))

        cache_key = f"analytics:course:{self.analytics.id}"
        self.assertIsNotNone(cache.get(cache_key), "Cache should be populated after first retrieve")

    def test_retrieve_returns_cached_data(self):
        """Second retrieve() returns same data (from cache)."""
        self.client.force_authenticate(user=self.instructor)
        r1 = self.client.get(reverse("course-analytics-detail", args=[self.analytics.id]))
        r2 = self.client.get(reverse("course-analytics-detail", args=[self.analytics.id]))

        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r1.data["total_enrollments"], r2.data["total_enrollments"])

    def test_recalculate_invalidates_cache(self):
        """recalculate() deletes cache so next retrieve() reflects updated data."""
        student = _user(User.ROLE_STUDENT, "student")
        Enrollment.objects.create(student=student, course=self.course)

        self.client.force_authenticate(user=self.instructor)

        # First retrieve — caches total_enrollments=5
        r1 = self.client.get(reverse("course-analytics-detail", args=[self.analytics.id]))
        self.assertEqual(r1.data["total_enrollments"], 5)

        # Recalculate — should update to 1 and invalidate cache
        self.client.post(reverse("course-analytics-recalculate", args=[self.analytics.id]))

        # Second retrieve — should show fresh data (total_enrollments=1 from DB)
        r2 = self.client.get(reverse("course-analytics-detail", args=[self.analytics.id]))
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["total_enrollments"], 1)

    def test_cache_key_is_per_analytics_object(self):
        """Different analytics objects have separate cache keys."""
        instructor2 = _user(User.ROLE_INSTRUCTOR, "instructor2")
        course2 = Course.objects.create(
            instructor=instructor2, title="Course 2", is_published=True
        )
        analytics2 = CourseAnalytics.objects.create(
            course=course2, total_enrollments=99
        )

        self.client.force_authenticate(user=self.instructor)
        self.client.get(reverse("course-analytics-detail", args=[self.analytics.id]))

        # analytics2 cache key should still be empty
        cache_key2 = f"analytics:course:{analytics2.id}"
        self.assertIsNone(cache.get(cache_key2), "Separate analytics should have separate cache keys")
