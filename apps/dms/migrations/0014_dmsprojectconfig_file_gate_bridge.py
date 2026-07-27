# Generated manually for FILE GATE Módulo 6 (dms_bridge).

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("dms", "0013_seed_transform_pipeline_templates"),
        ("projects", "0004_add_project_kind_and_dms_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="dmsprojectconfig",
            name="file_gate_accept",
            field=models.CharField(
                choices=[
                    ("passed", "Solo passed"),
                    ("passed_with_warnings", "passed o passed_with_warnings"),
                ],
                default="passed_with_warnings",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="dmsprojectconfig",
            name="file_gate_enabled",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="dmsprojectconfig",
            name="file_gate_linked_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="dmsprojectconfig",
            name="file_gate_linked_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dms_file_gate_links",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="dmsprojectconfig",
            name="file_gate_max_age_days",
            field=models.PositiveSmallIntegerField(default=7),
        ),
        migrations.AddField(
            model_name="dmsprojectconfig",
            name="file_gate_project",
            field=models.ForeignKey(
                blank=True,
                help_text="Proyecto FILE GATE vinculado (misma compañía).",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dms_bridge_configs",
                to="projects.project",
            ),
        ),
    ]
