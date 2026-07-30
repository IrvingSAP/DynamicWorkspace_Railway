# Generated manually for FILE MATCH Módulo 8 (gate bridge require A/B).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dms", "0014_dmsprojectconfig_file_gate_bridge"),
    ]

    operations = [
        migrations.AddField(
            model_name="dmsprojectconfig",
            name="file_gate_require_a",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="dmsprojectconfig",
            name="file_gate_require_b",
            field=models.BooleanField(default=False),
        ),
    ]
