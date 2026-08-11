from django.apps import AppConfig


class FileCleanConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.file_clean"
    verbose_name = "FILE CLEAN"

    def ready(self):
        from apps.file_clean import models  # noqa: F401
