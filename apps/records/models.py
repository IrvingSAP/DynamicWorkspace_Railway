import uuid

from django.conf import settings
from django.db import models

from apps.fields.models import FieldDefinition
from apps.projects.models import Project


class Record(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="records",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="records_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="records_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Registro"
        verbose_name_plural = "Registros"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["project", "is_deleted", "-updated_at"]),
        ]

    def __str__(self) -> str:
        return str(self.id)


class FieldValue(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(
        Record,
        on_delete=models.CASCADE,
        related_name="field_values",
    )
    field = models.ForeignKey(
        FieldDefinition,
        on_delete=models.PROTECT,
        related_name="field_values",
    )
    value_text = models.TextField(null=True, blank=True)
    value_number = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    value_date = models.DateField(null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)
    value_json = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Valor de campo"
        verbose_name_plural = "Valores de campo"
        constraints = [
            models.UniqueConstraint(
                fields=["record", "field"],
                name="records_fieldvalue_record_field_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["field", "value_text"]),
            models.Index(fields=["field", "value_number"]),
            models.Index(fields=["field", "value_date"]),
        ]

    def __str__(self) -> str:
        return f"{self.field.key} → {self.record_id}"
