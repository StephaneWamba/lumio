"""Tests for media management and video streaming"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from datetime import timedelta

from apps.users.models import User
from apps.courses.models import Course, Section, Lesson
from .models import VideoFile, CloudFrontSignedUrl


class VideoFileTests(TestCase):
    """Test video file upload and processing"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@example.com",
            name="Test Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Test Course",
            is_published=True,
        )
        self.section = Section.objects.create(
            course=self.course,
            title="Test Section",
            order=1,
        )
        self.lesson = Lesson.objects.create(
            section=self.section,
            title="Test Lesson",
            content="Test content",
            order=1,
        )

    def _initiate_upload(self, lesson=None, file_name="test-video.mp4", file_size=1024000000):
        """Helper: call the real initiate_upload endpoint and return the response."""
        if lesson is None:
            lesson = self.lesson
        self.client.force_authenticate(user=self.instructor)
        return self.client.post(
            reverse("videofile-initiate-upload"),
            {
                "lesson_id": lesson.id,
                "file_name": file_name,
                "file_size_bytes": file_size,
            },
        )

    def test_initiate_upload_requires_auth(self):
        """Test that upload initiation requires authentication"""
        self.client.force_authenticate(user=None)
        response = self.client.post(
            reverse("videofile-initiate-upload"),
            {
                "lesson_id": self.lesson.id,
                "file_name": "test-video.mp4",
                "file_size_bytes": 1024000000,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_initiate_upload_invalid_lesson(self):
        """Test upload initiation with non-existent lesson"""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("videofile-initiate-upload"),
            {
                "lesson_id": 99999,
                "file_name": "test-video.mp4",
                "file_size_bytes": 1024000000,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_initiate_upload_permission_denied(self):
        """Test upload initiation by non-instructor fails"""
        other_instructor = User.objects.create_user(
            email="other@example.com",
            name="Other Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.client.force_authenticate(user=other_instructor)
        response = self.client.post(
            reverse("videofile-initiate-upload"),
            {
                "lesson_id": self.lesson.id,
                "file_name": "test-video.mp4",
                "file_size_bytes": 1024000000,
            },
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_initiate_upload_as_owner(self):
        """Test instructor can initiate upload for own course"""
        response = self._initiate_upload()
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Real presigned URL must be present and non-empty
        self.assertIn("upload_url", response.data)
        self.assertTrue(response.data["upload_url"].startswith("https://"))
        self.assertIn("s3_key", response.data)
        self.assertTrue(response.data["s3_key"].startswith("raw/"))
        self.assertIn("video_id", response.data)
        # A real VideoFile record must exist in the DB
        video = VideoFile.objects.get(id=response.data["video_id"])
        self.assertEqual(video.lesson, self.lesson)
        self.assertEqual(video.status, VideoFile.STATUS_PENDING)

    def test_video_file_status(self):
        """Test video file status endpoint for a processing video"""
        # Create VideoFile via the real initiate_upload endpoint
        upload_resp = self._initiate_upload()
        self.assertEqual(upload_resp.status_code, status.HTTP_200_OK)
        video = VideoFile.objects.get(id=upload_resp.data["video_id"])
        # Manually advance to PROCESSING state (simulates FFmpeg worker picking it up)
        video.status = VideoFile.STATUS_PROCESSING
        video.save(update_fields=["status"])

        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("videofile-status", args=[video.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], VideoFile.STATUS_PROCESSING)
        self.assertFalse(response.data["hls_ready"])
        self.assertIsNone(response.data["hls_manifest"])

    def test_video_file_status_completed(self):
        """Test status endpoint when video is completed"""
        # Create VideoFile via the real initiate_upload endpoint
        upload_resp = self._initiate_upload()
        self.assertEqual(upload_resp.status_code, status.HTTP_200_OK)
        video = VideoFile.objects.get(id=upload_resp.data["video_id"])
        # Manually advance to COMPLETED state with HLS manifest (simulates FFmpeg worker)
        video.status = VideoFile.STATUS_COMPLETED
        video.s3_key_hls_manifest = "videos/hls/test/master.m3u8"
        video.hls_variants = [
            "videos/hls/test/480p.m3u8",
            "videos/hls/test/720p.m3u8",
        ]
        video.save(update_fields=["status", "s3_key_hls_manifest", "hls_variants"])

        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("videofile-status", args=[video.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], VideoFile.STATUS_COMPLETED)
        self.assertTrue(response.data["hls_ready"])
        self.assertEqual(response.data["hls_manifest"], "videos/hls/test/master.m3u8")


class SignedVideoUrlTests(TestCase):
    """Test signed CloudFront URL generation"""

    def setUp(self):
        """Set up test data"""
        self.client = APIClient()
        self.student = User.objects.create_user(
            email="student@example.com",
            name="Test Student",
            password="TestPassword123!",
            role=User.ROLE_STUDENT,
        )
        self.instructor = User.objects.create_user(
            email="instructor@example.com",
            name="Test Instructor",
            password="TestPassword123!",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=self.instructor,
            title="Test Course",
            is_published=True,
        )
        self.section = Section.objects.create(
            course=self.course,
            title="Test Section",
            order=1,
            is_published=True,
        )
        self.lesson = Lesson.objects.create(
            section=self.section,
            title="Test Lesson",
            content="Test content",
            order=1,
            is_published=True,
        )

    def _create_completed_video(self, lesson=None):
        """
        Create a VideoFile in STATUS_COMPLETED state via the initiate_upload endpoint
        then manually advance it to COMPLETED with an HLS manifest key.
        Returns the VideoFile instance.
        """
        if lesson is None:
            lesson = self.lesson
        self.client.force_authenticate(user=self.instructor)
        upload_resp = self.client.post(
            reverse("videofile-initiate-upload"),
            {
                "lesson_id": lesson.id,
                "file_name": "test-video.mp4",
                "file_size_bytes": 1024000000,
            },
        )
        self.assertEqual(upload_resp.status_code, status.HTTP_200_OK)
        video = VideoFile.objects.get(id=upload_resp.data["video_id"])
        video.status = VideoFile.STATUS_COMPLETED
        video.s3_key_hls_manifest = "videos/hls/test/master.m3u8"
        video.save(update_fields=["status", "s3_key_hls_manifest"])
        return video

    def test_get_video_url_requires_auth(self):
        """Test video URL endpoint requires authentication"""
        self.client.force_authenticate(user=None)
        response = self.client.get(reverse("signed-video-url-get-video-url", args=[self.lesson.id]))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_video_url_lesson_not_found(self):
        """Test video URL endpoint with non-existent lesson"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("signed-video-url-get-video-url", args=[99999]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_video_url_no_video(self):
        """Test video URL endpoint when lesson has no video"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("signed-video-url-get-video-url", args=[self.lesson.id]))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_video_url_not_processed(self):
        """Test video URL endpoint when video is still processing"""
        # Create VideoFile via the real initiate_upload endpoint (STATUS_PENDING by default)
        self.client.force_authenticate(user=self.instructor)
        upload_resp = self.client.post(
            reverse("videofile-initiate-upload"),
            {
                "lesson_id": self.lesson.id,
                "file_name": "test-video.mp4",
                "file_size_bytes": 1024000000,
            },
        )
        self.assertEqual(upload_resp.status_code, status.HTTP_200_OK)
        video = VideoFile.objects.get(id=upload_resp.data["video_id"])
        # Advance to PROCESSING (not yet COMPLETED)
        video.status = VideoFile.STATUS_PROCESSING
        video.save(update_fields=["status"])

        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("signed-video-url-get-video-url", args=[self.lesson.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("processing", response.data["error"].lower())

    def test_get_video_url_cached(self):
        """Test video URL endpoint returns cached signed URL if still valid"""
        self._create_completed_video()
        # Inject a cached (valid) signed URL record directly
        expires_at = timezone.now() + timedelta(hours=12)
        cached_url = (
            "https://d123456.cloudfront.net/master.m3u8"
            "?Expires=9999999999&Signature=abc&Key-Pair-Id=K123"
        )
        CloudFrontSignedUrl.objects.create(
            lesson=self.lesson,
            signed_url=cached_url,
            expires_at=expires_at,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("signed-video-url-get-video-url", args=[self.lesson.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("signed_url", response.data)
        self.assertIn("expires_at", response.data)
        # The cached URL must be returned verbatim (no re-signing)
        self.assertEqual(response.data["signed_url"], cached_url)

    def test_get_video_url_expired_cache(self):
        """Test video URL endpoint generates a new real CloudFront signed URL when cache expired"""
        self._create_completed_video()
        # Inject an already-expired cached URL record
        expired_at = timezone.now() - timedelta(hours=1)
        CloudFrontSignedUrl.objects.create(
            lesson=self.lesson,
            signed_url=(
                "https://d123456.cloudfront.net/master.m3u8"
                "?Expires=1&Signature=old&Key-Pair-Id=K123"
            ),
            expires_at=expired_at,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("signed-video-url-get-video-url", args=[self.lesson.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("signed_url", response.data)
        self.assertIn("expires_at", response.data)
        # A real CloudFront signed URL must contain the query parameters added by the signer
        signed_url = response.data["signed_url"]
        self.assertTrue(
            signed_url.startswith("https://"), f"Expected https:// URL, got: {signed_url}"
        )
        self.assertIn(
            "Signature=", signed_url, f"Expected CloudFront Signature param in URL: {signed_url}"
        )
        self.assertIn(
            "Key-Pair-Id=", signed_url, f"Expected Key-Pair-Id param in URL: {signed_url}"
        )
