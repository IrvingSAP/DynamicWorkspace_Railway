from django.contrib import admin

from apps.records.models import FieldValue, Record


class FieldValueInline(admin.TabularInline):
    model = FieldValue
    extra = 0
    readonly_fields = ("field", "value_text", "value_number", "value_date", "value_boolean", "updated_at")


@admin.register(Record)
class RecordAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "created_by", "is_deleted", "updated_at")
    list_filter = ("is_deleted", "project")
    search_fields = ("id", "project__slug")
    readonly_fields = ("created_at", "updated_at")
    inlines = [FieldValueInline]


@admin.register(FieldValue)
class FieldValueAdmin(admin.ModelAdmin):
    list_display = ("record", "field", "value_text", "value_number", "updated_at")
    list_filter = ("field__field_type",)
