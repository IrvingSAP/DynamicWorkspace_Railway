from django.db import migrations


def seed_value_generators(apps, schema_editor):
    ValueGeneratorType = apps.get_model("dms", "ValueGeneratorType")
    if ValueGeneratorType.objects.exists():
        return
    rows = [
        ("sequence_numeric", "Secuencia numérica", "sequence_numeric", 10),
        ("sequence_padded", "Secuencia con padding", "sequence_padded", 20),
        ("sequence_alphanumeric", "Secuencia alfanumérica", "sequence_alphanumeric", 30),
        ("sequence_template", "Plantilla con secuencia", "sequence_template", 40),
        ("unique_uuid", "UUID por fila", "unique_uuid", 50),
        ("unique_job_counter", "Correlativo por job", "unique_job_counter", 60),
        ("job_timestamp", "Fecha/hora de ejecución", "job_timestamp", 70),
        ("row_number", "Número de fila", "row_number", 80),
    ]
    for code, name, resolver, order in rows:
        ValueGeneratorType.objects.create(
            code=code,
            name=name,
            description="",
            resolver_key=resolver,
            param_schema=None,
            phase="mvp",
            sort_order=order,
            is_active=True,
        )


def unseed_value_generators(apps, schema_editor):
    ValueGeneratorType = apps.get_model("dms", "ValueGeneratorType")
    ValueGeneratorType.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("dms", "0008_value_generator_type"),
    ]

    operations = [
        migrations.RunPython(seed_value_generators, unseed_value_generators),
    ]
