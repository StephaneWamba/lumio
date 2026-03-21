"""Celery tasks for media — FFmpeg video transcoding pipeline."""

import os
import subprocess
import tempfile

import boto3
import structlog
from botocore.config import Config
from celery import shared_task
from django.conf import settings
from typing import Any

from .models import VideoFile

logger = structlog.get_logger(__name__)

# boto3 >= 1.35 sends ChecksumMode:ENABLED on HeadObject by default.
# Objects uploaded via presigned URLs have no stored checksum, causing S3 to
# return 400 Bad Request. Force "when_required" to restore pre-1.35 behaviour.
_S3_CONFIG = Config(
    request_checksum_calculation="when_required",
    response_checksum_validation="when_required",
)

HLS_VARIANTS = [
    {"name": "480p", "scale": "854:480", "bitrate": "1000k", "audio": "128k"},
    {"name": "720p", "scale": "1280:720", "bitrate": "2500k", "audio": "128k"},
    {"name": "1080p", "scale": "1920:1080", "bitrate": "5000k", "audio": "192k"},
]


def _s3_client():
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=_S3_CONFIG,
    )


@shared_task(
    name="media.transcode_video",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    time_limit=7200,      # 2 hours — overrides the global 30-min limit for this task
    soft_time_limit=6900, # soft limit fires SoftTimeLimitExceeded ~2 min before hard kill
)
def transcode_video(self: Any, video_file_id: int) -> dict:
    """
    Download raw video from S3, transcode to HLS (480p/720p/1080p), upload to processed bucket.
    Idempotent: marks VideoFile.status throughout for safe retry.
    """
    try:
        video = VideoFile.objects.get(id=video_file_id)
    except VideoFile.DoesNotExist:
        logger.error("transcode_video_not_found", video_file_id=video_file_id)
        return {"error": "VideoFile not found"}

    # Idempotency: skip if already completed
    if video.status == VideoFile.STATUS_COMPLETED:
        return {"skipped": True, "reason": "already completed"}

    video.status = VideoFile.STATUS_PROCESSING
    video.celery_task_id = self.request.id
    video.save(update_fields=["status", "celery_task_id"])

    s3 = _s3_client()
    lesson_id = video.lesson_id

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Download raw video from S3.
            # Use get_object() + stream instead of download_file() to bypass the
            # internal HeadObject call that download_file() makes — boto3 >= 1.35
            # adds x-amz-checksum-mode:ENABLED to HeadObject which S3 rejects with
            # 400 for objects uploaded via presigned URLs (no stored checksum).
            raw_path = os.path.join(tmpdir, "input.mp4")
            logger.info("downloading_raw_video", s3_key=video.s3_key_raw, lesson_id=lesson_id)
            obj = s3.get_object(Bucket=settings.S3_RAW_BUCKET, Key=video.s3_key_raw)
            with open(raw_path, "wb") as fh:
                for chunk in obj["Body"].iter_chunks(chunk_size=8 * 1024 * 1024):
                    fh.write(chunk)

            hls_keys = []
            manifest_lines = ["#EXTM3U", "#EXT-X-VERSION:3"]

            for variant in HLS_VARIANTS:
                variant_dir = os.path.join(tmpdir, variant["name"])
                os.makedirs(variant_dir)
                variant_m3u8 = os.path.join(variant_dir, "index.m3u8")
                segment_pattern = os.path.join(variant_dir, "seg%03d.ts")

                cmd = [
                    "ffmpeg",
                    "-y",
                    "-i",
                    raw_path,
                    "-vf",
                    f"scale={variant['scale']}",
                    "-c:v",
                    "libx264",
                    "-b:v",
                    variant["bitrate"],
                    "-c:a",
                    "aac",
                    "-b:a",
                    variant["audio"],
                    "-hls_time",
                    "6",
                    "-hls_list_size",
                    "0",
                    "-hls_segment_filename",
                    segment_pattern,
                    variant_m3u8,
                ]
                logger.info("ffmpeg_start", variant=variant["name"], lesson_id=lesson_id)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
                if result.returncode != 0:
                    raise RuntimeError(
                        f"FFmpeg failed for {variant['name']}: {result.stderr[-500:]}"
                    )

                # Upload all segment files and m3u8 to processed bucket
                s3_prefix = f"hls/{lesson_id}/{variant['name']}"
                variant_key = None
                for fname in os.listdir(variant_dir):
                    local_path = os.path.join(variant_dir, fname)
                    s3_key = f"{s3_prefix}/{fname}"
                    s3.upload_file(local_path, settings.S3_PROCESSED_BUCKET, s3_key)
                    if fname == "index.m3u8":
                        variant_key = s3_key

                if variant_key is None:
                    raise RuntimeError(
                        f"index.m3u8 not produced for variant {variant['name']}"
                    )
                hls_keys.append(variant_key)

                # Bandwidth value for master manifest (strip 'k', multiply by 1000)
                bw = int(variant["bitrate"].replace("k", "")) * 1000
                manifest_lines.append(
                    "#EXT-X-STREAM-INF:"
                    f"BANDWIDTH={bw},RESOLUTION={variant['scale'].replace(':', 'x')}"
                )
                manifest_lines.append(f"{variant['name']}/index.m3u8")

            # Write + upload master manifest
            master_key = f"hls/{lesson_id}/master.m3u8"
            master_path = os.path.join(tmpdir, "master.m3u8")
            with open(master_path, "w") as f:
                f.write("\n".join(manifest_lines) + "\n")
            s3.upload_file(master_path, settings.S3_PROCESSED_BUCKET, master_key)

        video.status = VideoFile.STATUS_COMPLETED
        video.s3_key_hls_manifest = master_key
        video.hls_variants = hls_keys
        video.error_message = None
        video.save(
            update_fields=["status", "s3_key_hls_manifest", "hls_variants", "error_message"]
        )

        logger.info("transcode_complete", lesson_id=lesson_id, master_key=master_key)
        return {"lesson_id": lesson_id, "master_key": master_key, "variants": hls_keys}

    except Exception as exc:
        error_msg = str(exc)
        logger.error(
            "transcode_failed",
            lesson_id=lesson_id,
            error=error_msg,
            attempt=self.request.retries + 1,
            max_attempts=self.max_retries + 1,
        )
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        # All retries exhausted — mark as permanently failed before propagating.
        logger.error("transcode_permanently_failed", lesson_id=lesson_id, video_id=video_file_id)
        video.status = VideoFile.STATUS_FAILED
        video.error_message = error_msg
        video.save(update_fields=["status", "error_message"])
        raise
