from django.contrib import admin

from apps.dms import models


@admin.register(models.SourceFileType)
class SourceFileTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "phase", "sort_order", "is_active")
    search_fields = ("code", "name")
    ordering = ("sort_order", "code")


@admin.register(models.TargetFileType)
class TargetFileTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "phase", "sort_order", "is_active")
    search_fields = ("code", "name")


@admin.register(models.CharsetEncoding)
class CharsetEncodingAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "charset_value", "is_auto_detect", "is_active")


@admin.register(models.LineEnding)
class LineEndingAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "sequence", "is_auto_detect", "is_active")


@admin.register(models.FieldContentType)
class FieldContentTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "phase", "is_active")


@admin.register(models.CaptureBoundaryMode)
class CaptureBoundaryModeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "applies_to", "phase", "is_active")


@admin.register(models.TargetFieldDataType)
class TargetFieldDataTypeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "requires_format", "is_active")


@admin.register(models.ExecutionErrorCode)
class ExecutionErrorCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "phase", "severity", "is_active")


@admin.register(models.FilenamePatternVariable)
class FilenamePatternVariableAdmin(admin.ModelAdmin):
    list_display = ("code", "syntax", "resolver_key", "is_active")


@admin.register(models.DmsProjectConfig)
class DmsProjectConfigAdmin(admin.ModelAdmin):
    list_display = ("project", "visibility", "current_version", "updated_at")
    search_fields = ("project__slug", "project__name")
    list_filter = ("visibility",)


@admin.register(models.DmsMappingVersion)
class DmsMappingVersionAdmin(admin.ModelAdmin):
    list_display = ("project", "version_number", "status", "published_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("project__slug", "project__name")
    ordering = ("-updated_at",)


@admin.register(models.DmsSourceProfile)
class DmsSourceProfileAdmin(admin.ModelAdmin):
    list_display = ("version", "file_type_code", "updated_at")
    search_fields = ("version__project__slug", "file_type_code")


@admin.register(models.DmsTargetProfile)
class DmsTargetProfileAdmin(admin.ModelAdmin):
    list_display = ("version", "file_type_code", "updated_at")
    search_fields = ("version__project__slug", "file_type_code")


@admin.register(models.DmsFieldMappingSet)
class DmsFieldMappingSetAdmin(admin.ModelAdmin):
    list_display = ("version", "updated_at")
    search_fields = ("version__project__slug",)


@admin.register(models.DmsSampleFile)
class DmsSampleFileAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "project", "size_bytes", "created_at")
    search_fields = ("original_filename", "project__slug")


@admin.register(models.DmsExecutionJob)
class DmsExecutionJobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "project",
        "status",
        "input_original_filename",
        "created_at",
    )
    list_filter = ("status", "job_type")
    search_fields = ("project__slug", "input_original_filename")
