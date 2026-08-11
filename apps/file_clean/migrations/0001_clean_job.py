# Generated manually for CleanJob

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("projects", "0007_add_file_clean_kind"),
        ("dms", "0016_transform_ops_numeric_integer"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CleanJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("published_version_number", models.PositiveIntegerField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "En cola"),
                            ("running", "En curso"),
                            ("completed", "Completado"),
                            ("failed", "Fallido"),
                        ],
                        default="running",
                        max_length=16,
                    ),
                ),
                ("dry_run", models.BooleanField(default=False)),
                ("idempotency_key", models.CharField(blank=True, db_index=True, default="", max_length=128)),
                ("input_original_filename", models.CharField(blank=True, default="", max_length=255)),
                ("input_stored_path", models.CharField(blank=True, default="", max_length=512)),
                ("input_size_bytes", models.BigIntegerField(default=0)),
                ("input_content_hash", models.CharField(blank=True, default="", max_length=64)),
                ("input_mime_type", models.CharField(blank=True, default="", max_length=128)),
                ("output_filename", models.CharField(blank=True, default="", max_length=255)),
                ("output_stored_path", models.CharField(blank=True, default="", max_length=512)),
                ("output_size_bytes", models.BigIntegerField(default=0)),
                ("output_content_hash", models.CharField(blank=True, default="", max_length=64)),
                ("change_log_path", models.CharField(blank=True, default="", max_length=512)),
                ("metrics", models.JSONField(blank=True, default=dict)),
                ("preview", models.JSONField(blank=True, default=dict)),
                ("rules_snapshot", models.JSONField(blank=True, default=list)),
                ("error_message", models.TextField(blank=True, default="")),
                ("error_code", models.CharField(blank=True, default="", max_length=64)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "executed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="file_clean_jobs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="file_clean_jobs",
                        to="projects.project",
                    ),
                ),
                (
                    "published_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="file_clean_jobs",
                        to="dms.dmsmappingversion",
                    ),
                ),
            ],
            options={
                "verbose_name": "FILE CLEAN — Job",
                "verbose_name_plural": "FILE CLEAN — Jobs",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="cleanjob",
            constraint=models.UniqueConstraint(
                condition=~models.Q(idempotency_key=""),
                fields=("project", "idempotency_key"),
                name="file_clean_job_idempotency_uniq",
            ),
        ),
    ]
