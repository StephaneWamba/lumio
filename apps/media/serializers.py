"""Media serializers"""
from rest_framework import serializers
from .models import VideoFile, CloudFrontSignedUrl


class VideoFileSerializer(serializers.ModelSerializer):
    """Video file serializer"""

    class Meta:
        model = VideoFile
        fields = [
            "id",
            "lesson",
            "file_size_bytes",
            "duration_seconds",
            "status",
            "s3_key_hls_manifest",
            "hls_variants",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "s3_key_raw",
            "s3_key_hls_manifest",
            "hls_variants",
            "status",
            "created_at",
            "updated_at",
        ]


class CloudFrontSignedUrlSerializer(serializers.ModelSerializer):
    """CloudFront signed URL serializer"""

    class Meta:
        model = CloudFrontSignedUrl
        fields = [
            "lesson",
            "signed_url",
            "expires_at",
        ]
        read_only_fields = [
            "signed_url",
            "expires_at",
        ]


class VideoUploadInitiateSerializer(serializers.Serializer):
    """Request presigned S3 upload URL"""

    lesson_id = serializers.IntegerField()
    file_name = serializers.CharField(max_length=255)
    file_size_bytes = serializers.IntegerField()
