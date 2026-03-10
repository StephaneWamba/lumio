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

    def test_initiate_upload_requires_auth(self):
        """Test that upload initiation requires authentication"""
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
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("videofile-initiate-upload"),
            {
                "lesson_id": self.lesson.id,
                "file_name": "test-video.mp4",
                "file_size_bytes": 1024000000,
            },
        )
        # Currently returns 501 as S3 presigned URL is TODO
        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)
        self.assertIn("error", response.data)

    def test_video_file_status(self):
        """Test video file status endpoint"""
        video = VideoFile.objects.create(
            lesson=self.lesson,
            s3_key_raw="videos/test-video.mp4",
            file_size_bytes=1024000000,
            duration_seconds=3600,
            status=VideoFile.STATUS_PROCESSING,
        )
        self.client.force_authenticate(user=self.instructor)
        response = self.client.get(reverse("videofile-status", args=[video.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], VideoFile.STATUS_PROCESSING)
        self.assertFalse(response.data["hls_ready"])

    def test_video_file_status_completed(self):
        """Test status endpoint when video is completed"""
        video = VideoFile.objects.create(
            lesson=self.lesson,
            s3_key_raw="videos/test-video.mp4",
            s3_key_hls_manifest="videos/hls/test/master.m3u8",
            hls_variants=[
                "videos/hls/test/480p.m3u8",
                "videos/hls/test/720p.m3u8",
            ],
            status=VideoFile.STATUS_COMPLETED,
        )
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

    def test_get_video_url_requires_auth(self):
        """Test video URL endpoint requires authentication"""
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
        video = VideoFile.objects.create(
            lesson=self.lesson,
            s3_key_raw="videos/test-video.mp4",
            status=VideoFile.STATUS_PROCESSING,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("signed-video-url-get-video-url", args=[self.lesson.id]))
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("processing", response.data["error"].lower())

    def test_get_video_url_cached(self):
        """Test video URL endpoint returns cached signed URL if valid"""
        video = VideoFile.objects.create(
            lesson=self.lesson,
            s3_key_raw="videos/test-video.mp4",
            s3_key_hls_manifest="videos/hls/test/master.m3u8",
            status=VideoFile.STATUS_COMPLETED,
        )
        expires_at = timezone.now() + timedelta(hours=12)
        CloudFrontSignedUrl.objects.create(
            lesson=self.lesson,
            signed_url="https://d123456.cloudfront.net/master.m3u8?signature=...",
            expires_at=expires_at,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("signed-video-url-get-video-url", args=[self.lesson.id]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("signed_url", response.data)
        self.assertIn("expires_at", response.data)

    def test_get_video_url_expired_cache(self):
        """Test video URL endpoint generates new URL when cached URL expired"""
        video = VideoFile.objects.create(
            lesson=self.lesson,
            s3_key_raw="videos/test-video.mp4",
            s3_key_hls_manifest="videos/hls/test/master.m3u8",
            status=VideoFile.STATUS_COMPLETED,
        )
        expires_at = timezone.now() - timedelta(hours=1)  # Already expired
        CloudFrontSignedUrl.objects.create(
            lesson=self.lesson,
            signed_url="https://d123456.cloudfront.net/master.m3u8?signature=...",
            expires_at=expires_at,
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.get(reverse("signed-video-url-get-video-url", args=[self.lesson.id]))
        # Currently returns 501 as CloudFront signed URL generation is TODO
        self.assertEqual(response.status_code, status.HTTP_501_NOT_IMPLEMENTED)
        self.assertIn("error", response.data)
