from django.apps import AppConfig


class FileWatchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.file_watch"
    label = "file_watch"
    verbose_name = "File Watch"

    def ready(self):
        from apps.file_watch import signals  # noqa: F401
