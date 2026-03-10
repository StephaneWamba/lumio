"""Media app URLs"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import VideoFileViewSet, SignedVideoUrlView

router = DefaultRouter()
router.register(r"videos", VideoFileViewSet, basename="videofile")
router.register(r"signed-video-urls", SignedVideoUrlView, basename="signed-video-url")

urlpatterns = [
    path("", include(router.urls)),
    # Custom route for getting signed video URL: /api/media/lessons/{lesson_id}/video-url
    path(
        "lessons/<int:lesson_id>/video-url/",
        SignedVideoUrlView.as_view({"get": "get_video_url"}),
        name="signed-video-url-get-video-url",
    ),
]
