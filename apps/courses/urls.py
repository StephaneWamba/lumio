"""Courses app URLs"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CourseViewSet, SectionViewSet, LessonViewSet

router = DefaultRouter()
router.register(r"courses", CourseViewSet, basename="course")

urlpatterns = [
    path("", include(router.urls)),
    # Nested routes: /courses/{course_id}/sections/, /sections/{section_id}/lessons/
    path(
        "courses/<int:course_id>/sections/",
        SectionViewSet.as_view(
            {
                "get": "list",
                "post": "create",
            }
        ),
        name="course-sections",
    ),
    path(
        "courses/<int:course_id>/sections/<int:section_id>/",
        SectionViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="section-detail",
    ),
    path(
        "courses/<int:course_id>/sections/<int:section_id>/lessons/",
        LessonViewSet.as_view(
            {
                "get": "list",
                "post": "create",
            }
        ),
        name="section-lessons",
    ),
    path(
        "courses/<int:course_id>/sections/<int:section_id>/lessons/<int:pk>/",
        LessonViewSet.as_view(
            {
                "get": "retrieve",
                "put": "update",
                "patch": "partial_update",
                "delete": "destroy",
            }
        ),
        name="lesson-detail",
    ),
]
