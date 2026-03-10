"""Search app URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SearchViewSet, SearchQueryViewSet

router = DefaultRouter()
router.register(r"", SearchViewSet, basename="search")
router.register(r"queries", SearchQueryViewSet, basename="search-query")

urlpatterns = [
    path("", include(router.urls)),
]
