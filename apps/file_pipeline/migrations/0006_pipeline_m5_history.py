from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("file_pipeline", "0005_pipeline_m4_run"),
    ]

    operations = [
        migrations.AddField(
            model_name="pipelinerun",
            name="api_client_label",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="pipelinerun",
            name="client_ip",
            field=models.CharField(blank=True, default="", max_length=45),
        ),
        migrations.AddField(
            model_name="pipelinerun",
            name="correlation_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="pipelinerun",
            name="idempotency_key",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="pipelinerun",
            name="user_agent",
            field=models.CharField(blank=True, default="", max_length=300),
        ),
    ]
