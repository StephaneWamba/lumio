"""Celery tasks for media — FFmpeg video transcoding pipeline."""

import os
import subprocess
import tempfile

import boto3
import structlog
from celery import shared_task
from django.conf import settings

from .models import VideoFile

logger = structlog.get_logger(__name__)

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
    )


@shared_task(name="media.transcode_video", bind=True, max_retries=3, default_retry_delay=60)
def transcode_video(self, video_file_id: int) -> dict:
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
            # Download raw video from S3
            raw_path = os.path.join(tmpdir, "input.mp4")
            logger.info("downloading_raw_video", s3_key=video.s3_key_raw, lesson_id=lesson_id)
            s3.download_file(settings.S3_RAW_BUCKET, video.s3_key_raw, raw_path)

            hls_keys = []
            manifest_lines = ["#EXTM3U", "#EXT-X-VERSION:3"]

            for variant in HLS_VARIANTS:
                variant_dir = os.path.join(tmpdir, variant["name"])
                os.makedirs(variant_dir)
                variant_m3u8 = os.path.join(variant_dir, "index.m3u8")
                segment_pattern = os.path.join(variant_dir, "seg%03d.ts")

                cmd = [
                    "ffmpeg", "-y", "-i", raw_path,
                    "-vf", f"scale={variant['scale']}",
                    "-c:v", "libx264", "-b:v", variant["bitrate"],
                    "-c:a", "aac", "-b:a", variant["audio"],
                    "-hls_time", "6",
                    "-hls_list_size", "0",
                    "-hls_segment_filename", segment_pattern,
                    variant_m3u8,
                ]
                logger.info("ffmpeg_start", variant=variant["name"], lesson_id=lesson_id)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg failed for {variant['name']}: {result.stderr[-500:]}")

                # Upload all segment files and m3u8 to processed bucket
                s3_prefix = f"hls/{lesson_id}/{variant['name']}"
                for fname in os.listdir(variant_dir):
                    local_path = os.path.join(variant_dir, fname)
                    s3_key = f"{s3_prefix}/{fname}"
                    s3.upload_file(local_path, settings.S3_PROCESSED_BUCKET, s3_key)
                    if fname == "index.m3u8":
                        variant_key = s3_key

                hls_keys.append(variant_key)

                # Bandwidth value for master manifest (strip 'k', multiply by 1000)
                bw = int(variant["bitrate"].replace("k", "")) * 1000
                manifest_lines.append(
                    f"#EXT-X-STREAM-INF:BANDWIDTH={bw},RESOLUTION={variant['scale'].replace(':', 'x')}"
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
        video.save(update_fields=["status", "s3_key_hls_manifest", "hls_variants", "error_message"])

        logger.info("transcode_complete", lesson_id=lesson_id, master_key=master_key)
        return {"lesson_id": lesson_id, "master_key": master_key, "variants": hls_keys}

    except Exception as exc:
        logger.error("transcode_failed", lesson_id=lesson_id, error=str(exc))
        video.status = VideoFile.STATUS_FAILED
        video.error_message = str(exc)
        video.save(update_fields=["status", "error_message"])
        raise self.retry(exc=exc)
