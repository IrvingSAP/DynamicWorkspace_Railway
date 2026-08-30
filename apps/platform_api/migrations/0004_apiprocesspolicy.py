import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("company", "0001_initial"),
        ("platform_api", "0003_apiclientauditevent"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiProcessPolicy",
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
                ("max_upload_bytes", models.PositiveIntegerField(default=52428800)),
                ("rate_per_minute", models.PositiveIntegerField(default=60)),
                ("artifact_ttl_hours", models.PositiveIntegerField(default=24)),
                ("allowed_extensions", models.JSONField(default=list)),
                ("webhook_host_allowlist", models.JSONField(default=list)),
                ("require_published", models.BooleanField(default=True)),
                ("dry_run_counts_in_dashboard", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_process_policy",
                        to="company.company",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="api_process_policies_updated",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Política de proceso API",
                "verbose_name_plural": "Políticas de proceso API",
            },
        ),
    ]
