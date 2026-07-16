# Generated manually for File intake MVP

import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("dms", "0006_field_mapping_set"),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DmsSampleFile",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("original_filename", models.CharField(max_length=255)),
                ("stored_path", models.CharField(max_length=500)),
                ("size_bytes", models.PositiveBigIntegerField(default=0)),
                ("content_hash", models.CharField(blank=True, default="", max_length=64)),
                ("mime_type", models.CharField(blank=True, default="", max_length=120)),
                ("suggestions", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dms_sample_files",
                        to="projects.project",
                    ),
                ),
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dms_sample_uploads",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="sample_files",
                        to="dms.dmsmappingversion",
                    ),
                ),
            ],
            options={
                "verbose_name": "Archivo muestra DMS",
                "verbose_name_plural": "Archivos muestra DMS",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="DmsExecutionJob",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "job_type",
                    models.CharField(
                        choices=[("preview", "Preview"), ("full", "Completo")],
                        default="full",
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("uploaded", "Subido"),
                            ("queued", "En cola"),
                            ("running", "En ejecución"),
                            ("completed", "Completado"),
                            ("partial", "Parcial"),
                            ("failed", "Fallido"),
                            ("cancelled", "Cancelado"),
                        ],
                        default="uploaded",
                        max_length=16,
                    ),
                ),
                ("input_original_filename", models.CharField(blank=True, default="", max_length=255)),
                ("input_stored_path", models.CharField(blank=True, default="", max_length=500)),
                ("input_size_bytes", models.PositiveBigIntegerField(default=0)),
                ("input_content_hash", models.CharField(blank=True, default="", max_length=64)),
                ("input_mime_type", models.CharField(blank=True, default="", max_length=120)),
                ("input_suggestions", models.JSONField(blank=True, default=dict)),
                ("output_filename", models.CharField(blank=True, default="", max_length=255)),
                ("output_stored_path", models.CharField(blank=True, default="", max_length=500)),
                ("output_size_bytes", models.PositiveBigIntegerField(default=0)),
                ("report_path", models.CharField(blank=True, default="", max_length=500)),
                ("rows_read", models.PositiveIntegerField(default=0)),
                ("rows_ok", models.PositiveIntegerField(default=0)),
                ("rows_rejected", models.PositiveIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "executed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="dms_execution_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dms_execution_jobs",
                        to="projects.project",
                    ),
                ),
                (
                    "version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="execution_jobs",
                        to="dms.dmsmappingversion",
                    ),
                ),
            ],
            options={
                "verbose_name": "Job de ejecución DMS",
                "verbose_name_plural": "Jobs de ejecución DMS",
                "ordering": ["-created_at"],
            },
        ),
    ]
