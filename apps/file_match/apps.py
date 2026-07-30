from django.apps import AppConfig


class FileMatchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.file_match"
    verbose_name = "FILE MATCH"

    def ready(self):
        # Ensure models are imported for migrations / admin discovery.
        from apps.file_match import models  # noqa: F401
