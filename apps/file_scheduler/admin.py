from django.contrib import admin

from apps.file_scheduler.models import (
    Schedule,
    ScheduleAuditEvent,
    ScheduleMembership,
    ScheduleNotifyDispatch,
    ScheduleTick,
)


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "company", "status", "visibility", "updated_at")
    list_filter = ("status", "visibility")
    search_fields = ("slug", "name")


@admin.register(ScheduleMembership)
class ScheduleMembershipAdmin(admin.ModelAdmin):
    list_display = ("schedule", "user", "role", "is_active")
    list_filter = ("role", "is_active")


@admin.register(ScheduleAuditEvent)
class ScheduleAuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "schedule", "actor")
    list_filter = ("event",)
    readonly_fields = (
        "company",
        "schedule",
        "event",
        "payload",
        "actor",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ScheduleTick)
class ScheduleTickAdmin(admin.ModelAdmin):
    list_display = ("scheduled_for", "status", "schedule", "error_code")
    list_filter = ("status",)
    readonly_fields = (
        "company",
        "schedule",
        "scheduled_for",
        "status",
        "error_code",
        "user_message",
        "correlation_id",
        "job_id",
        "pipeline_run_id",
        "payload",
        "created_at",
    )


@admin.register(ScheduleNotifyDispatch)
class ScheduleNotifyDispatchAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "schedule", "ref_id")
    list_filter = ("kind",)
    readonly_fields = ("schedule", "kind", "ref_id", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
