from django.apps import AppConfig


class FileSchedulerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.file_scheduler"
    label = "file_scheduler"
    verbose_name = "File Scheduler"

    def ready(self):
        from apps.file_scheduler import signals  # noqa: F401
