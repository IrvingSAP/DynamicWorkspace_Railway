import uuid

from django.db import models

from apps.projects.models import Project


class FieldDefinition(models.Model):
    TYPE_TEXT_SHORT = "text_short"
    TYPE_TEXT_LONG = "text_long"
    TYPE_INTEGER = "integer"
    TYPE_DECIMAL = "decimal"
    TYPE_DATE = "date"
    TYPE_DATETIME = "datetime"
    TYPE_BOOLEAN = "boolean"
    TYPE_SELECT = "select"

    FIELD_TYPE_CHOICES = [
        (TYPE_TEXT_SHORT, "Texto corto"),
        (TYPE_TEXT_LONG, "Texto largo"),
        (TYPE_INTEGER, "Entero"),
        (TYPE_DECIMAL, "Decimal"),
        (TYPE_DATE, "Fecha"),
        (TYPE_DATETIME, "Fecha y hora"),
        (TYPE_BOOLEAN, "Sí / No"),
        (TYPE_SELECT, "Lista de opciones"),
    ]

    TEXT_TYPES = {TYPE_TEXT_SHORT, TYPE_TEXT_LONG}
    NUMBER_TYPES = {TYPE_INTEGER, TYPE_DECIMAL}

    DEFAULT_MAX_LENGTH = {
        TYPE_TEXT_SHORT: 255,
        TYPE_TEXT_LONG: 2000,
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="field_definitions",
    )
    key = models.SlugField(max_length=100)
    label = models.CharField(max_length=200)
    field_type = models.CharField(max_length=30, choices=FIELD_TYPE_CHOICES)
    options = models.JSONField(default=dict, blank=True)
    max_length = models.PositiveIntegerField(null=True, blank=True)
    required = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Definición de campo"
        verbose_name_plural = "Definiciones de campo"
        ordering = ["sort_order", "label"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "key"],
                name="fields_fielddefinition_project_key_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.key} ({self.project.slug})"
