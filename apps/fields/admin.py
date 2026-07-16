from django.contrib import admin

from apps.fields.models import FieldDefinition


@admin.register(FieldDefinition)
class FieldDefinitionAdmin(admin.ModelAdmin):
    list_display = (
        "key",
        "label",
        "field_type",
        "project",
        "sort_order",
        "required",
        "is_active",
        "updated_at",
    )
    list_filter = ("field_type", "is_active", "required")
    search_fields = ("key", "label", "project__name", "project__slug")
    raw_id_fields = ("project",)
