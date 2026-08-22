from django.apps import AppConfig


class FilePipelineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.file_pipeline"
    label = "file_pipeline"
    verbose_name = "File Pipeline"
