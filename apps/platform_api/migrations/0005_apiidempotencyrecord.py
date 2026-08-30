import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("company", "0001_initial"),
        ("platform_api", "0004_apiprocesspolicy"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiIdempotencyRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("key", models.CharField(max_length=128)),
                ("request_hash", models.CharField(max_length=64)),
                ("job_id", models.UUIDField()),
                ("envelope", models.JSONField(default=dict)),
                ("user_message", models.CharField(blank=True, default="", max_length=240)),
                ("http_status", models.PositiveSmallIntegerField(default=200)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="idempotency_records",
                        to="platform_api.apiclient",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_idempotency_records",
                        to="company.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Registro de idempotencia API",
                "verbose_name_plural": "Registros de idempotencia API",
            },
        ),
        migrations.AddConstraint(
            model_name="apiidempotencyrecord",
            constraint=models.UniqueConstraint(
                fields=("company", "client", "key"),
                name="platform_api_unique_idempotency_key",
            ),
        ),
    ]
