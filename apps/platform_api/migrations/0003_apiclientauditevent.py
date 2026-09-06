import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platform_api", "0002_apiclient_description"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ApiClientAuditEvent",
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
                    "action",
                    models.CharField(
                        choices=[
                            ("created", "Alta"),
                            ("updated", "Cambio de configuración"),
                            ("key_rotated", "Rotación de key"),
                            ("revoked", "Revocación"),
                            ("key_revealed", "Key mostrada (un uso)"),
                        ],
                        max_length=32,
                    ),
                ),
                ("summary", models.CharField(max_length=240)),
                ("before", models.JSONField(blank=True, null=True)),
                ("after", models.JSONField(blank=True, null=True)),
                ("ip_address", models.CharField(blank=True, default="", max_length=64)),
                ("user_agent", models.CharField(blank=True, default="", max_length=256)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="api_client_audit_events",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "client",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="audit_events",
                        to="platform_api.apiclient",
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="api_client_audit_events",
                        to="company.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Evento de auditoría API",
                "verbose_name_plural": "Eventos de auditoría API",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="apiclientauditevent",
            index=models.Index(
                fields=["company", "-created_at"],
                name="pa_audit_company_at",
            ),
        ),
        migrations.AddIndex(
            model_name="apiclientauditevent",
            index=models.Index(
                fields=["client", "-created_at"],
                name="pa_audit_client_at",
            ),
        ),
    ]
