from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("platform_api", "0001_api_client_m1"),
    ]

    operations = [
        migrations.AddField(
            model_name="apiclient",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
    ]
