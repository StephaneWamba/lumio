"""Media views: video upload, transcoding, signed URLs"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
import structlog

from apps.courses.models import Lesson
from .models import VideoFile, CloudFrontSignedUrl
from .serializers import VideoFileSerializer, VideoUploadInitiateSerializer
from .video_service import generate_presigned_upload_url, generate_cloudfront_signed_url
from .tasks import transcode_video

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

        result = generate_presigned_upload_url(lesson_id, file_name, file_size)

        # Create VideoFile record to track transcoding state
        video, _ = VideoFile.objects.get_or_create(
            lesson=lesson,
            defaults={"s3_key_raw": result["s3_key"], "file_size_bytes": file_size},
        )
        if video.s3_key_raw != result["s3_key"]:
            video.s3_key_raw = result["s3_key"]
            video.status = VideoFile.STATUS_PENDING
            video.save(update_fields=["s3_key_raw", "status"])

        logger.info("video_upload_initiated", lesson_id=lesson_id, s3_key=result["s3_key"])
        return Response(
            {
                "upload_url": result["upload_url"],
                "s3_key": result["s3_key"],
                "expires_in": result["expires_in"],
                "video_id": video.id,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def trigger_transcode(self, request, pk=None):
        """Trigger FFmpeg transcoding after frontend finishes S3 upload."""
        video = self.get_object()

        if video.lesson.section.course.instructor != request.user:
            return Response(
                {"error": "You can only transcode videos in your own courses"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if video.status == VideoFile.STATUS_COMPLETED:
            return Response({"status": "already_completed"}, status=status.HTTP_200_OK)

        if video.status == VideoFile.STATUS_PROCESSING:
            return Response({"status": "already_processing"}, status=status.HTTP_200_OK)

        transcode_video.delay(video.id)
        logger.info("transcode_triggered", video_id=video.id, lesson_id=video.lesson.id)
        return Response({"status": "queued", "video_id": video.id}, status=status.HTTP_202_ACCEPTED)

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

        # Generate new signed CloudFront URL and cache it
        hls_key = video.s3_key_hls_manifest
        if hls_key is None:
            return Response(
                {"error": "HLS manifest key not available"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        signed_url, expires_at = generate_cloudfront_signed_url(hls_key)

        CloudFrontSignedUrl.objects.update_or_create(
            lesson=lesson,
            defaults={"signed_url": signed_url, "expires_at": expires_at},
        )

        logger.info("video_url_generated", lesson_id=lesson_id, user_id=request.user.id)
        return Response({"signed_url": signed_url, "expires_at": expires_at})
