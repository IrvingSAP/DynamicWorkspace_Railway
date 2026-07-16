from django.db import migrations


def seed_pipeline_templates(apps, schema_editor):
    TransformPipelineTemplate = apps.get_model("dms", "TransformPipelineTemplate")
    if TransformPipelineTemplate.objects.exists():
        return
    templates = [
        (
            "normalize_text",
            "Normalizar texto",
            "trim + upper",
            [{"op": "trim"}, {"op": "upper"}],
            10,
        ),
        (
            "date_iso",
            "Fecha ISO",
            "date_format %Y-%m-%d",
            [
                {"op": "trim"},
                {
                    "op": "date_format",
                    "format": "%Y-%m-%d",
                    "input_formats": ["%d/%m/%Y", "%Y-%m-%d"],
                },
            ],
            20,
        ),
        (
            "blank_to_na",
            "Vacío → N/A",
            "default_if_empty",
            [{"op": "default_if_empty", "value": "N/A"}],
            30,
        ),
        (
            "pad_left_5",
            "Pad izquierda 5",
            "pad_left con ceros",
            [{"op": "pad_left", "char": "0", "length": 5}],
            40,
        ),
    ]
    for code, name, desc, pipeline, order in templates:
        TransformPipelineTemplate.objects.create(
            code=code,
            name=name,
            description=desc,
            pipeline=pipeline,
            sort_order=order,
            is_active=True,
        )


def unseed_pipeline_templates(apps, schema_editor):
    TransformPipelineTemplate = apps.get_model("dms", "TransformPipelineTemplate")
    TransformPipelineTemplate.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("dms", "0012_transform_pipeline_template"),
    ]

    operations = [
        migrations.RunPython(seed_pipeline_templates, unseed_pipeline_templates),
    ]
