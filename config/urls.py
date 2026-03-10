"""URL Configuration for lumio project"""
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

# Health check endpoint
def health_check(request):
    """Simple health check for ECS load balancer"""
    return __import__('django.http', fromlist=['JsonResponse']).JsonResponse(
        {"status": "healthy"},
        status=200,
    )

urlpatterns = [
    # Health check (for ECS ALB)
    path("health/", health_check, name="health_check"),

    # Admin
    path("admin/", admin.site.urls),

    # API documentation
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),

    # API routes
    path("api/v1/", include([
        # Users (auth, OAuth, profiles)
        path("auth/", include("apps.users.urls")),

        # Courses (course builder, content management)
        path("courses/", include("apps.courses.urls")),

        # Media (video upload, transcoding status)
        path("media/", include("apps.media.urls")),

        # Enrollments (enrollment, progress)
        path("enrollments/", include("apps.enrollments.urls")),

        # Assessments (quizzes, attempts)
        path("assessments/", include("apps.assessments.urls")),

        # Cohorts (cohort management, drip publishing)
        path("cohorts/", include("apps.cohorts.urls")),

        # Certificates (cert generation, verification)
        path("certificates/", include("apps.certificates.urls")),

        # Notifications (email sequences)
        path("notifications/", include("apps.notifications.urls")),

        # Payments (Stripe, marketplace)
        path("payments/", include("apps.payments.urls")),

        # Search (full-text search, filtering, caching)
        path("search/", include("apps.search.urls")),

        # Analytics (instructor analytics, progress tracking)
        path("analytics/", include("apps.analytics.urls")),
    ])),
]
