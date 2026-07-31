from django.apps import AppConfig


class StructureScoutConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.structure_scout"
    verbose_name = "STRUCTURE SCOUT"

    def ready(self):
        from apps.structure_scout import models  # noqa: F401
