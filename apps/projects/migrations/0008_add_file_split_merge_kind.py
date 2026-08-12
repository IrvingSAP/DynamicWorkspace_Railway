from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("projects", "0007_add_file_clean_kind"),
    ]

    operations = [
        migrations.AlterField(
            model_name="project",
            name="project_kind",
            field=models.CharField(
                choices=[
                    ("workspace", "Workspace (tabla)"),
                    ("dms", "DMS (FilePipe)"),
                    ("file_gate", "FILE GATE (Validador)"),
                    ("reverse", "Reverse Studio (Emisor)"),
                    ("file_match", "FILE MATCH (Conciliador)"),
                    ("structure_scout", "STRUCTURE SCOUT (Explorador)"),
                    ("file_clean", "FILE CLEAN (Limpieza)"),
                    ("file_split_merge", "FILE SPLIT/MERGE (Partición)"),
                ],
                default="workspace",
                max_length=16,
            ),
        ),
    ]
