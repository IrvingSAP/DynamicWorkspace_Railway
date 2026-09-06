from django.contrib import admin

from apps.file_watch.models import (
    Watch,
    WatchAuditEvent,
    WatchBatch,
    WatchMembership,
    WatchNotifyDispatch,
)


@admin.register(Watch)
class WatchAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "company", "status", "visibility", "source_kind", "updated_at")
    list_filter = ("status", "visibility", "source_kind")
    search_fields = ("slug", "name")


@admin.register(WatchMembership)
class WatchMembershipAdmin(admin.ModelAdmin):
    list_display = ("watch", "user", "role", "is_active")
    list_filter = ("role", "is_active")


@admin.register(WatchBatch)
class WatchBatchAdmin(admin.ModelAdmin):
    list_display = ("created_at", "status", "watch", "original_filename", "content_hash")
    list_filter = ("status",)
    search_fields = ("original_filename", "content_hash")
    readonly_fields = (
        "company",
        "watch",
        "original_filename",
        "content_hash",
        "storage_key",
        "byte_size",
        "status",
        "source_kind",
        "detected_at",
        "ingested_at",
        "consumed_at",
        "consumed_by",
        "error_code",
        "job_id",
        "pipeline_run_id",
        "correlation_id",
        "payload",
        "created_at",
        "updated_at",
    )


@admin.register(WatchAuditEvent)
class WatchAuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "event", "watch", "actor")
    list_filter = ("event",)
    readonly_fields = (
        "company",
        "watch",
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


@admin.register(WatchNotifyDispatch)
class WatchNotifyDispatchAdmin(admin.ModelAdmin):
    list_display = ("created_at", "kind", "watch", "ref_id")
    list_filter = ("kind",)
    readonly_fields = ("watch", "kind", "ref_id", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
