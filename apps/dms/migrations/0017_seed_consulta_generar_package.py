from django.db import migrations


def seed_consulta_generar(apps, schema_editor):
    PermissionPackage = apps.get_model("dms", "PermissionPackage")
    PermissionPackage.objects.update_or_create(
        code="consulta_generar",
        defaults={
            "name": "Consulta-Generar",
            "description": "Consulta del proyecto y ejecutar / generar salidas.",
            "maps_to_role": "CG",
            "permissions": ["view", "execute"],
            "sort_order": 45,
            "is_active": True,
        },
    )


def unseed_consulta_generar(apps, schema_editor):
    PermissionPackage = apps.get_model("dms", "PermissionPackage")
    PermissionPackage.objects.filter(code="consulta_generar").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("dms", "0016_transform_ops_numeric_integer"),
    ]

    operations = [
        migrations.RunPython(seed_consulta_generar, unseed_consulta_generar),
    ]
