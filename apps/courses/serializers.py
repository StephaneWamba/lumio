"""Course serializers"""

from rest_framework import serializers
from apps.users.serializers import UserSerializer
from .models import Course, Section, Lesson


class LessonSerializer(serializers.ModelSerializer):
    """Lesson serializer"""

    class Meta:
        model = Lesson
        fields = [
            "id",
            "title",
            "description",
            "content",
            "video_s3_key",
            "video_duration_seconds",
            "is_video_processed",
            "order",
            "is_published",
            "prerequisite_lesson",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_video_processed",
            "created_at",
            "updated_at",
        ]


class SectionSerializer(serializers.ModelSerializer):
    """Section serializer with nested lessons"""

    lessons = LessonSerializer(many=True, read_only=True)

    class Meta:
        model = Section
        fields = [
            "id",
            "course",
            "title",
            "description",
            "order",
            "is_published",
            "lessons",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class CourseListSerializer(serializers.ModelSerializer):
    """Course list serializer (lightweight)"""

    instructor = UserSerializer(read_only=True)
    section_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "description",
            "thumbnail_url",
            "price",
            "duration_minutes",
            "is_published",
            "instructor",
            "section_count",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]

    def get_section_count(self, obj):
        return obj.sections.filter(is_published=True).count()


class CourseDetailSerializer(serializers.ModelSerializer):
    """Course detail serializer with nested sections and lessons"""

    instructor = UserSerializer(read_only=True)
    sections = SectionSerializer(many=True, read_only=True)

    class Meta:
        model = Course
        fields = [
            "id",
            "title",
            "description",
            "thumbnail_url",
            "price",
            "duration_minutes",
            "is_published",
            "is_archived",
            "instructor",
            "sections",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]


class CourseCreateUpdateSerializer(serializers.ModelSerializer):
    """Course create/update serializer"""

    class Meta:
        model = Course
        fields = [
            "title",
            "description",
            "thumbnail_url",
            "price",
            "duration_minutes",
            "is_published",
        ]
