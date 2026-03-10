"""Cohorts app admin configuration"""

from django.contrib import admin
from .models import Cohort, CohortMember, DripSchedule


@admin.register(Cohort)
class CohortAdmin(admin.ModelAdmin):
    """Admin for cohorts"""

    list_display = ["course", "name", "start_date", "end_date", "is_open", "is_active"]
    list_filter = ["is_open", "start_date", "end_date"]
    search_fields = ["course__title", "name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CohortMember)
class CohortMemberAdmin(admin.ModelAdmin):
    """Admin for cohort members"""

    list_display = ["cohort", "student", "is_active", "joined_at", "left_at"]
    list_filter = ["cohort", "is_active", "joined_at"]
    search_fields = ["student__email", "student__name", "cohort__name"]
    readonly_fields = ["joined_at", "created_at", "updated_at"]


@admin.register(DripSchedule)
class DripScheduleAdmin(admin.ModelAdmin):
    """Admin for drip schedules"""

    list_display = ["cohort", "drip_type", "days_after_start", "is_released", "released_at"]
    list_filter = ["drip_type", "is_released", "is_active", "released_at"]
    search_fields = ["cohort__name", "lesson__title", "section__title"]
    readonly_fields = ["released_at", "created_at", "updated_at"]
