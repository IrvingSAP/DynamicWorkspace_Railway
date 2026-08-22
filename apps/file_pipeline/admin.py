from django.contrib import admin

from apps.file_pipeline.models import (
    PipelineCompanyKindFlag,
    PipelineDefinition,
    PipelineMembership,
    PipelineStepKind,
    PipelineVersion,
    PipelineRun,
)


@admin.register(PipelineDefinition)
class PipelineDefinitionAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "company", "status", "visibility", "updated_at")
    list_filter = ("status", "visibility")
    search_fields = ("slug", "name")


@admin.register(PipelineMembership)
class PipelineMembershipAdmin(admin.ModelAdmin):
    list_display = ("pipeline", "user", "role", "is_active")
    list_filter = ("role", "is_active")


@admin.register(PipelineStepKind)
class PipelineStepKindAdmin(admin.ModelAdmin):
    list_display = ("kind", "label", "pipeline_enabled", "mvp_phase", "status")
    list_filter = ("pipeline_enabled", "status", "mvp_phase")
    search_fields = ("kind", "label", "project_kind")


@admin.register(PipelineCompanyKindFlag)
class PipelineCompanyKindFlagAdmin(admin.ModelAdmin):
    list_display = ("company", "step_kind", "included", "updated_at")
    list_filter = ("included",)


@admin.register(PipelineVersion)
class PipelineVersionAdmin(admin.ModelAdmin):
    list_display = ("pipeline", "version_number", "status", "published_at")
    list_filter = ("status",)


@admin.register(PipelineRun)
class PipelineRunAdmin(admin.ModelAdmin):
    list_display = ("pipeline", "status", "trigger_source", "created_at")
    list_filter = ("status", "trigger_source")
