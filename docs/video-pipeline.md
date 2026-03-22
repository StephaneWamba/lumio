# Video Pipeline

## Upload Flow

```
Client → POST /api/v1/media/initiate-upload/
       ← presigned PUT URL (15min TTL)

Client → PUT video to S3 (lumio-raw-uploads)   # direct, no Django proxy

Client → POST /api/v1/media/complete-upload/
       ← video_file_id, status: processing
```

## Transcoding

The `transcode_video` Celery task runs exclusively on the `lumio-ffmpeg` worker:

1. Stream raw file from S3 in 8MB chunks (`get_object` + `iter_chunks`) — avoids loading multi-GB files into memory.
2. Run FFmpeg to produce three HLS renditions: 1080p, 720p, 480p. Each rendition gets its own directory of `.ts` segments and an `index.m3u8` playlist.
3. Upload all segments and playlists to S3 (`lumio-processed-media`).
4. Write a master playlist referencing all renditions.
5. Update `VideoFile.status = ready` and store the master playlist S3 key.

On failure the task retries up to 3 times with 60s delay. After exhausting retries, `status` is set to `failed` with the error message stored.

## Playback

```
Client → GET /api/v1/media/{id}/playback-url/
       ← signed CloudFront URL (5min TTL, cached in Redis)
```

The API checks enrollment before issuing the URL. Students never receive a raw S3 URL.

## boto3 Checksum Note

boto3 ≥ 1.35 sends `x-amz-checksum-mode: ENABLED` on `HeadObject` by default. Objects uploaded via presigned PUT have no stored checksum, causing S3 to return 400. The S3 client is configured with:

```python
Config(
    request_checksum_calculation="when_required",
    response_checksum_validation="when_required",
)
```

`get_object` is used instead of `download_file` to bypass the `HeadObject` call entirely.
