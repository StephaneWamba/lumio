"""Users app admin configuration"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, InstructorProfile, CorporateManagerProfile


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ["email", "name", "role", "is_active", "date_joined"]
    list_filter = ["role", "is_active", "date_joined"]
    search_fields = ["email", "name"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("name", "avatar_url")}),
        ("Permissions", {"fields": ("role", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Email", {"fields": ("email_verified", "email_verified_at")}),
        ("Important dates", {"fields": ("date_joined", "updated_at", "last_login")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2"),
        }),
    )
    ordering = ["-date_joined"]
    readonly_fields = ["date_joined", "updated_at", "last_login"]


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "is_approved", "stripe_onboarded", "created_at"]
    list_filter = ["is_approved", "stripe_onboarded", "created_at"]
    search_fields = ["user__email", "user__name"]
    readonly_fields = ["created_at", "updated_at"]
    fieldsets = (
        (None, {"fields": ("user", "bio", "website")}),
        ("Approval", {"fields": ("is_approved", "approved_at", "approved_by")}),
        ("Payments", {"fields": ("stripe_account_id", "stripe_onboarded")}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(CorporateManagerProfile)
class CorporateManagerProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "company_name", "team_size", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__email", "company_name"]
    readonly_fields = ["created_at", "updated_at"]
