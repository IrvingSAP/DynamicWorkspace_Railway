from django.contrib import admin

from apps.platform_api.models import (
    ApiClient,
    ApiClientAuditEvent,
    ApiIdempotencyRecord,
    ApiProcessPolicy,
    ApiWebhookDelivery,
)


@admin.register(ApiClient)
class ApiClientAdmin(admin.ModelAdmin):
    list_display = ("code", "company", "environment", "status", "created_at")
    list_filter = ("environment", "status")
    search_fields = ("code", "name", "description", "public_id")
    readonly_fields = (
        "public_id",
        "secret_hash",
        "key_hint",
        "last_used_at",
        "revoked_at",
        "created_at",
        "updated_at",
    )


@admin.register(ApiClientAuditEvent)
class ApiClientAuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "client", "actor", "company")
    list_filter = ("action",)
    search_fields = ("summary", "client__code")
    readonly_fields = (
        "company",
        "client",
        "action",
        "summary",
        "before",
        "after",
        "actor",
        "ip_address",
        "user_agent",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApiProcessPolicy)
class ApiProcessPolicyAdmin(admin.ModelAdmin):
    list_display = ("company", "max_upload_bytes", "rate_per_minute", "artifact_ttl_hours", "updated_at")
    search_fields = ("company__name_short",)
    readonly_fields = ("require_published", "dry_run_counts_in_dashboard", "updated_at")


@admin.register(ApiIdempotencyRecord)
class ApiIdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ("created_at", "client", "key", "job_id", "http_status")
    search_fields = ("key",)
    readonly_fields = (
        "company",
        "client",
        "key",
        "request_hash",
        "job_id",
        "envelope",
        "user_message",
        "http_status",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ApiWebhookDelivery)
class ApiWebhookDeliveryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "client", "event", "status", "attempt_count", "response_status")
    list_filter = ("status", "event")
    search_fields = ("event", "client__code")
    readonly_fields = (
        "company",
        "client",
        "event",
        "job_id",
        "payload",
        "status",
        "attempt_count",
        "max_attempts",
        "response_status",
        "last_error",
        "next_retry_at",
        "delivered_at",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
