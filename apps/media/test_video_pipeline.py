"""Tests for video pipeline — hits real S3 and real CloudFront signing."""

import os
import uuid

import boto3
import requests
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.courses.models import Course, Section, Lesson
from apps.media.models import VideoFile, CloudFrontSignedUrl


class PresignedUploadTests(TestCase):
    """Presigned S3 upload URL — hits real S3."""

    def setUp(self):
        self.client: APIClient = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor@media-test.com",
            name="Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=self.instructor, title="Video Course", is_published=True
        )
        self.section = Section.objects.create(course=self.course, title="S1", order=1)
        self.lesson = Lesson.objects.create(section=self.section, title="L1", order=1)

    def test_initiate_upload_returns_real_presigned_url(self):
        """Returns a genuine S3 presigned PUT URL that accepts a PUT request."""
        self.client.force_authenticate(user=self.instructor)
        response = self.client.post(
            reverse("videofile-initiate-upload"),
            {"lesson_id": self.lesson.id, "file_name": "test.mp4", "file_size_bytes": 16},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        upload_url = response.data["upload_url"]
        self.assertTrue(upload_url.startswith("https://"), f"Expected HTTPS URL, got: {upload_url}")
        self.assertIn(settings.S3_RAW_BUCKET, upload_url)

        # Verify the presigned URL actually works — PUT 16 bytes
        put_resp = requests.put(
            upload_url,
            data=b"lumio-test-video",
            headers={"Content-Type": "video/mp4", "Content-Length": "16"},
            timeout=10,
        )
        self.assertIn(put_resp.status_code, [200, 204], f"S3 PUT failed: {put_resp.text}")

    def test_initiate_upload_creates_pending_video_file(self):
        """VideoFile record created in STATUS_PENDING after calling endpoint."""
        self.client.force_authenticate(user=self.instructor)
        self.client.post(
            reverse("videofile-initiate-upload"),
            {"lesson_id": self.lesson.id, "file_name": "test.mp4", "file_size_bytes": 16},
        )

        self.assertTrue(VideoFile.objects.filter(lesson=self.lesson).exists())
        video = VideoFile.objects.get(lesson=self.lesson)
        self.assertEqual(video.status, VideoFile.STATUS_PENDING)
        self.assertIn(f"raw/{self.lesson.id}/", video.s3_key_raw)

    def test_non_owner_cannot_get_upload_url(self):
        """Instructor who doesn't own the course gets 403."""
        other = User.objects.create_user(
            email="other@media-test.com",
            name="Other",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.client.force_authenticate(user=other)
        response = self.client.post(
            reverse("videofile-initiate-upload"),
            {"lesson_id": self.lesson.id, "file_name": "x.mp4", "file_size_bytes": 100},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CloudFrontSignedUrlTests(TestCase):
    """CloudFront signed URL generation — uses real private key."""

    def setUp(self):
        self.client: APIClient = APIClient()
        self.instructor = User.objects.create_user(
            email="instructor2@media-test.com",
            name="Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.student = User.objects.create_user(
            email="student@media-test.com",
            name="Student",
            password="pass",
            role=User.ROLE_STUDENT,
        )
        self.course = Course.objects.create(
            instructor=self.instructor, title="Video Course 2", is_published=True
        )
        self.section = Section.objects.create(course=self.course, title="S1", order=1)
        self.lesson = Lesson.objects.create(section=self.section, title="L1", order=1)
        self.video = VideoFile.objects.create(
            lesson=self.lesson,
            s3_key_raw="raw/1/input.mp4",
            s3_key_hls_manifest="hls/1/master.m3u8",
            status=VideoFile.STATUS_COMPLETED,
        )

    def test_signed_url_generated_with_real_key(self):
        """CloudFront signer produces a URL with Signature, Key-Pair-Id, Expires params."""
        from apps.media.video_service import generate_cloudfront_signed_url

        signed_url, expires_at = generate_cloudfront_signed_url("hls/1/master.m3u8")

        self.assertIn("Signature=", signed_url)
        self.assertIn("Key-Pair-Id=", signed_url)
        self.assertIn("Expires=", signed_url)
        self.assertIn(settings.CLOUDFRONT_KEY_PAIR_ID, signed_url)
        self.assertIsNotNone(expires_at)

    def test_get_video_url_endpoint_returns_signed_url(self):
        """GET endpoint calls real signer and returns CloudFront URL."""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(
            reverse("signed-video-url-get-video-url", kwargs={"lesson_id": self.lesson.id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        signed_url = response.data["signed_url"]
        self.assertIn("Signature=", signed_url)
        self.assertIn(settings.CLOUDFRONT_DOMAIN, signed_url)

    def test_signed_url_cached_in_db(self):
        """After first call, CloudFrontSignedUrl record is created."""
        self.client.force_authenticate(user=self.student)
        self.client.get(
            reverse("signed-video-url-get-video-url", kwargs={"lesson_id": self.lesson.id})
        )

        self.assertTrue(CloudFrontSignedUrl.objects.filter(lesson=self.lesson).exists())

    def test_pending_video_returns_400(self):
        """Non-completed video returns 400 regardless of credentials."""
        self.video.status = VideoFile.STATUS_PROCESSING
        self.video.save()
        self.client.force_authenticate(user=self.student)

        response = self.client.get(
            reverse("signed-video-url-get-video-url", kwargs={"lesson_id": self.lesson.id})
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class TranscodeVideoTaskTests(TestCase):
    """FFmpeg transcode task — hits real S3, runs real FFmpeg."""

    def setUp(self):
        self.instructor = User.objects.create_user(
            email="instructor3@media-test.com",
            name="Instructor",
            password="pass",
            role=User.ROLE_INSTRUCTOR,
        )
        self.course = Course.objects.create(
            instructor=self.instructor, title="T", is_published=True
        )
        self.section = Section.objects.create(course=self.course, title="S", order=1)
        self.lesson = Lesson.objects.create(section=self.section, title="L", order=1)

    def _upload_tiny_test_video(self, s3_key: str) -> None:
        """Upload a minimal valid MP4 to S3 raw bucket for transcoding tests."""
        # Minimal valid ftyp+mdat MP4 (valid enough for FFmpeg to process)
        # We generate it via FFmpeg itself: 1-second black silent video
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            tmp_path = f.name

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=black:size=128x72:duration=1:rate=1",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=44100:cl=mono",
                "-t",
                "1",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                tmp_path,
            ],
            capture_output=True,
            check=True,
        )

        s3 = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        s3.upload_file(tmp_path, settings.S3_RAW_BUCKET, s3_key)
        os.unlink(tmp_path)

    def test_transcode_completes_and_uploads_hls_to_s3(self):
        """Full end-to-end: upload raw video → transcode → HLS in S3."""
        s3_key = f"raw/{self.lesson.id}/{uuid.uuid4().hex}.mp4"
        self._upload_tiny_test_video(s3_key)

        video = VideoFile.objects.create(
            lesson=self.lesson,
            s3_key_raw=s3_key,
            status=VideoFile.STATUS_PENDING,
        )

        from apps.media.tasks import transcode_video

        transcode_video(video.id)

        video.refresh_from_db()
        self.assertEqual(video.status, VideoFile.STATUS_COMPLETED)
        self.assertIsNotNone(video.s3_key_hls_manifest)
        self.assertGreater(len(video.hls_variants), 0)

        # Verify master manifest exists in S3
        s3 = boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
        obj = s3.get_object(Bucket=settings.S3_PROCESSED_BUCKET, Key=video.s3_key_hls_manifest)
        self.assertIn(b"#EXTM3U", obj["Body"].read())

    def test_transcode_idempotent_on_completed_video(self):
        """Calling task again on completed video returns skipped=True, no re-transcode."""
        video = VideoFile.objects.create(
            lesson=self.lesson,
            s3_key_raw="raw/x/input.mp4",
            s3_key_hls_manifest="hls/x/master.m3u8",
            status=VideoFile.STATUS_COMPLETED,
        )

        from apps.media.tasks import transcode_video

        result = transcode_video(video.id)
        self.assertEqual(result.get("skipped"), True)
