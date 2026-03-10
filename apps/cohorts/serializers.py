"""Cohorts serializers"""
from rest_framework import serializers
from apps.users.serializers import UserSerializer
from apps.courses.serializers import CourseListSerializer
from .models import Cohort, CohortMember, DripSchedule


class CohortListSerializer(serializers.ModelSerializer):
    """Cohort list with member count"""

    course_title = serializers.CharField(source="course.title", read_only=True)
    member_count = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Cohort
        fields = [
            "id",
            "course",
            "course_title",
            "name",
            "start_date",
            "end_date",
            "is_open",
            "member_count",
            "max_students",
            "is_active",
        ]
        read_only_fields = ["id"]

    def get_member_count(self, obj):
        """Count active members"""
        return obj.member_count

    def get_is_active(self, obj):
        """Check if cohort is active"""
        return obj.is_active


class CohortDetailSerializer(serializers.ModelSerializer):
    """Cohort detail with members"""

    course = CourseListSerializer(read_only=True)
    members = serializers.SerializerMethodField()

    class Meta:
        model = Cohort
        fields = [
            "id",
            "course",
            "name",
            "description",
            "start_date",
            "end_date",
            "max_students",
            "is_open",
            "members",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_members(self, obj):
        """Get active members"""
        members = obj.members.filter(is_active=True)
        return CohortMemberSerializer(members, many=True, read_only=True).data


class CohortMemberSerializer(serializers.ModelSerializer):
    """Cohort member serializer"""

    student = UserSerializer(read_only=True)

    class Meta:
        model = CohortMember
        fields = [
            "id",
            "student",
            "is_active",
            "joined_at",
            "left_at",
        ]
        read_only_fields = ["id", "joined_at"]


class DripScheduleSerializer(serializers.ModelSerializer):
    """Drip schedule serializer"""

    content_title = serializers.SerializerMethodField()
    scheduled_release_time = serializers.SerializerMethodField()
    is_ready_to_release = serializers.SerializerMethodField()

    class Meta:
        model = DripSchedule
        fields = [
            "id",
            "cohort",
            "drip_type",
            "lesson",
            "section",
            "content_title",
            "days_after_start",
            "release_at",
            "scheduled_release_time",
            "is_active",
            "is_released",
            "released_at",
            "is_ready_to_release",
        ]
        read_only_fields = [
            "id",
            "released_at",
            "scheduled_release_time",
            "is_ready_to_release",
        ]

    def get_content_title(self, obj):
        """Get the title of the content being dripped"""
        if obj.lesson:
            return obj.lesson.title
        elif obj.section:
            return obj.section.title
        return "Unknown"

    def get_scheduled_release_time(self, obj):
        """Get calculated release time"""
        return obj.scheduled_release_time

    def get_is_ready_to_release(self, obj):
        """Check if ready to release"""
        return obj.is_ready_to_release


class JoinCohortSerializer(serializers.Serializer):
    """Request to join a cohort"""

    cohort_id = serializers.IntegerField()
