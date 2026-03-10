"""Search app URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SearchViewSet, SearchQueryViewSet

router = DefaultRouter()
router.register(r"queries", SearchQueryViewSet, basename="search-query")
router.register(r"", SearchViewSet, basename="search")

urlpatterns = [
    path("", include(router.urls)),
]
