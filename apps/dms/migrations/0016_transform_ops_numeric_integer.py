from django.db import migrations


def upsert_numeric_ops(apps, schema_editor):
    TransformOperation = apps.get_model("dms", "TransformOperation")

    TransformOperation.objects.filter(code="number_format").update(
        name="Numérico con decimales",
        param_schema=["decimal_places", "thousands_sep", "decimal_sep"],
        sort_order=150,
        is_active=True,
    )

    TransformOperation.objects.update_or_create(
        code="number_integer",
        defaults={
            "name": "Numérico entero",
            "description": "Entero sin decimales (edad, cantidades).",
            "resolver_key": "number_integer",
            "param_schema": [],
            "phase": "phase_2",
            "sort_order": 155,
            "is_active": True,
        },
    )


def revert_numeric_ops(apps, schema_editor):
    TransformOperation = apps.get_model("dms", "TransformOperation")
    TransformOperation.objects.filter(code="number_integer").delete()
    TransformOperation.objects.filter(code="number_format").update(
        name="Formato numérico",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("dms", "0015_dmsprojectconfig_file_gate_require_sides"),
    ]

    operations = [
        migrations.RunPython(upsert_numeric_ops, revert_numeric_ops),
    ]
