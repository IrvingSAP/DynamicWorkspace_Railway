from django.db import migrations

from apps.dms.catalogs.services.seed_data import seed_catalogs, unseed_catalogs


class Migration(migrations.Migration):
    dependencies = [
        ("dms", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_catalogs, unseed_catalogs),
    ]
