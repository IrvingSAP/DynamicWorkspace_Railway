from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0008_add_file_split_merge_kind"),
    ]

    operations = [
        migrations.AlterField(
            model_name="projectmembership",
            name="role",
            field=models.CharField(
                choices=[
                    ("PA", "Admin de proyecto"),
                    ("ED", "Editor"),
                    ("CO", "Consulta"),
                    ("GE", "Generar"),
                    ("CG", "Consulta-Generar"),
                ],
                max_length=2,
            ),
        ),
    ]
