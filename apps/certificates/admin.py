"""Certificates app admin configuration"""
from django.contrib import admin
from .models import CertificateTemplate, CertificateAward, EarnedCertificate


@admin.register(CertificateTemplate)
class CertificateTemplateAdmin(admin.ModelAdmin):
    """Admin for certificate templates"""

    list_display = [
        "course",
        "title",
        "institution_name",
        "is_active",
        "created_at",
    ]
    list_filter = ["is_active", "created_at"]
    search_fields = ["course__title", "title", "institution_name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CertificateAward)
class CertificateAwardAdmin(admin.ModelAdmin):
    """Admin for certificate award criteria"""

    list_display = [
        "course",
        "condition",
        "minimum_score",
        "is_active",
        "created_at",
    ]
    list_filter = ["condition", "is_active", "created_at"]
    search_fields = ["course__title"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(EarnedCertificate)
class EarnedCertificateAdmin(admin.ModelAdmin):
    """Admin for earned certificates"""

    list_display = [
        "certificate_number",
        "enrollment",
        "issued_at",
        "is_revoked",
        "created_at",
    ]
    list_filter = ["is_revoked", "issued_at", "created_at"]
    search_fields = [
        "certificate_number",
        "enrollment__student__email",
        "enrollment__course__title",
    ]
    readonly_fields = [
        "certificate_number",
        "rendered_content",
        "created_at",
        "updated_at",
    ]
