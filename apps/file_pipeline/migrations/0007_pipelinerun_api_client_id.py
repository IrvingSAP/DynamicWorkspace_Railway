from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("file_pipeline", "0006_pipeline_m5_history"),
    ]

    operations = [
        migrations.AddField(
            model_name="pipelinerun",
            name="api_client_id",
            field=models.CharField(blank=True, default="", max_length=36),
        ),
    ]
