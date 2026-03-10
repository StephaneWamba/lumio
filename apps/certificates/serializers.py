"""Certificates app serializers"""

from rest_framework import serializers
from .models import CertificateTemplate, CertificateAward, EarnedCertificate
from apps.courses.serializers import CourseListSerializer
from apps.users.serializers import UserSerializer


class CertificateTemplateSerializer(serializers.ModelSerializer):
    """Serializer for certificate templates"""

    course = CourseListSerializer(read_only=True)
    course_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = CertificateTemplate
        fields = [
            "id",
            "course",
            "course_id",
            "title",
            "description",
            "content",
            "institution_name",
            "signature_text",
            "logo_url",
            "color_primary",
            "color_accent",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class CertificateAwardSerializer(serializers.ModelSerializer):
    """Serializer for certificate award criteria"""

    course = CourseListSerializer(read_only=True)
    course_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = CertificateAward
        fields = [
            "id",
            "course",
            "course_id",
            "condition",
            "minimum_score",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]


class EarnedCertificateListSerializer(serializers.ModelSerializer):
    """Serializer for listing earned certificates"""

    student_name = serializers.CharField(
        source="enrollment.student.name",
        read_only=True,
    )
    course_title = serializers.CharField(
        source="enrollment.course.title",
        read_only=True,
    )
    course_id = serializers.IntegerField(
        source="enrollment.course.id",
        read_only=True,
    )

    class Meta:
        model = EarnedCertificate
        fields = [
            "id",
            "certificate_number",
            "student_name",
            "course_title",
            "course_id",
            "issued_at",
            "is_revoked",
        ]
        read_only_fields = fields


class EarnedCertificateDetailSerializer(serializers.ModelSerializer):
    """Serializer for earned certificate detail view"""

    student = UserSerializer(
        source="enrollment.student",
        read_only=True,
    )
    course = CourseListSerializer(
        source="enrollment.course",
        read_only=True,
    )
    template = CertificateTemplateSerializer(read_only=True)

    class Meta:
        model = EarnedCertificate
        fields = [
            "id",
            "certificate_number",
            "student",
            "course",
            "template",
            "rendered_content",
            "issued_at",
            "is_revoked",
            "revoked_at",
            "revocation_reason",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "certificate_number",
            "rendered_content",
            "created_at",
            "updated_at",
        ]
