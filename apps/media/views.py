"""Media views: video upload, transcoding, signed URLs"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import boto3
import structlog

from apps.courses.models import Lesson
from .models import VideoFile, CloudFrontSignedUrl
from .serializers import (
    VideoFileSerializer,
    CloudFrontSignedUrlSerializer,
    VideoUploadInitiateSerializer,
)

logger = structlog.get_logger()


class VideoFileViewSet(viewsets.ReadOnlyModelViewSet):
    """Video file management (read-only for students, write via upload endpoint)"""

    queryset = VideoFile.objects.all()
    serializer_class = VideoFileSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["post"])
    def initiate_upload(self, request):
        """Get presigned S3 URL for video upload"""
        serializer = VideoUploadInitiateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        lesson_id = serializer.validated_data["lesson_id"]
        file_name = serializer.validated_data["file_name"]
        file_size = serializer.validated_data["file_size_bytes"]

        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check instructor permission
        if lesson.section.course.instructor != request.user:
            return Response(
                {"error": "You can only upload videos to your own courses"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # TODO: Generate presigned upload URL via S3
        # For now, return placeholder
        logger.info(
            "video_upload_initiated",
            lesson_id=lesson_id,
            file_name=file_name,
            file_size=file_size,
        )

        return Response(
            {
                "message": "Video upload endpoint coming in Phase 3",
                "error": "Presigned S3 upload not yet implemented",
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )

    @action(detail=True, methods=["get"])
    def status(self, request, pk=None):
        """Get video processing status"""
        video = self.get_object()
        return Response(
            {
                "status": video.status,
                "error": video.error_message,
                "hls_ready": video.status == VideoFile.STATUS_COMPLETED,
                "hls_manifest": video.s3_key_hls_manifest,
            }
        )


class SignedVideoUrlView(viewsets.ViewSet):
    """Get signed CloudFront URL for video access"""

    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"], url_path="lessons/(?P<lesson_id>[^/.]+)/video-url")
    def get_video_url(self, request, lesson_id=None):
        """Get signed CloudFront URL for lesson video"""
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {"error": "Lesson not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if video is processed
        try:
            video = lesson.video_file
        except VideoFile.DoesNotExist:
            return Response(
                {"error": "Video not found for this lesson"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if video.status != VideoFile.STATUS_COMPLETED:
            return Response(
                {"error": f"Video is {video.status}, not ready for playback"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check cached signed URL
        try:
            signed_url_obj = lesson.cloudfront_signed_url
            from django.utils import timezone
            if signed_url_obj.expires_at > timezone.now():
                return Response(
                    {
                        "signed_url": signed_url_obj.signed_url,
                        "expires_at": signed_url_obj.expires_at,
                    }
                )
        except CloudFrontSignedUrl.DoesNotExist:
            pass

        # TODO: Generate new signed CloudFront URL
        logger.info(
            "video_access_requested",
            lesson_id=lesson_id,
            user_id=request.user.id,
        )

        return Response(
            {
                "message": "Video URL endpoint coming in Phase 3",
                "error": "CloudFront signed URLs not yet implemented",
            },
            status=status.HTTP_501_NOT_IMPLEMENTED,
        )
