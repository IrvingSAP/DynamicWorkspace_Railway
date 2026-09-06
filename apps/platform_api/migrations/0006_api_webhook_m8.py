import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("company", "0001_initial"),
        ("platform_api", "0005_apiidempotencyrecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiclient",
            name="webhook_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="apiclient",
            name="webhook_events",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="apiclient",
            name="webhook_secret",
            field=models.CharField(blank=True, default="", max_length=128),
        ),
        migrations.AddField(
            model_name="apiclient",
            name="webhook_secret_hint",
            field=models.CharField(blank=True, default="", max_length=8),
        ),
        migrations.AddField(
            model_name="apiclient",
            name="webhook_url",
            field=models.URLField(blank=True, default="", max_length=500),
        ),
        migrations.CreateModel(
            name="ApiWebhookDelivery",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("event", models.CharField(max_length=32)),
                ("job_id", models.UUIDField()),
                ("payload", models.JSONField(default=dict)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendiente"),
                            ("delivered", "Entregado"),
                            ("failed", "Agotado"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("max_attempts", models.PositiveSmallIntegerField(default=5)),
                ("response_status", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("last_error", models.CharField(blank=True, default="", max_length=240)),
                ("next_retry_at", models.DateTimeField(blank=True, null=True)),
                ("delivered_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="webhook_deliveries",
                        to="platform_api.apiclient",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_webhook_deliveries",
                        to="company.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Entrega webhook API",
                "verbose_name_plural": "Entregas webhook API",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="apiwebhookdelivery",
            index=models.Index(fields=["status", "next_retry_at"], name="pa_wh_retry"),
        ),
        migrations.AddIndex(
            model_name="apiwebhookdelivery",
            index=models.Index(fields=["client", "-created_at"], name="pa_wh_client_at"),
        ),
    ]
