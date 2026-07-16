from django.db import migrations


def seed_packages_and_ops(apps, schema_editor):
    PermissionPackage = apps.get_model("dms", "PermissionPackage")
    TransformOperation = apps.get_model("dms", "TransformOperation")

    if not PermissionPackage.objects.exists():
        packages = [
            ("admin", "Admin", "PA", ["view", "create", "update", "delete", "execute", "manage_members", "grant_admin"], 10),
            ("editor", "Editor", "ED", ["view", "create", "update"], 20),
            ("viewer", "Consulta", "CO", ["view"], 30),
            ("executor", "Generar / ejecutar", "GE", ["view", "execute"], 40),
            ("view_only", "Solo lectura", "CO", ["view"], 50),
            ("update_view", "Ver y editar", "ED", ["view", "update"], 60),
            ("update_view_create", "Ver, editar y crear", "ED", ["view", "update", "create"], 70),
            ("full_crud", "CRUD completo", "ED", ["view", "create", "update", "delete"], 80),
        ]
        for code, name, role, perms, order in packages:
            PermissionPackage.objects.create(
                code=code,
                name=name,
                description="",
                maps_to_role=role,
                permissions=perms,
                sort_order=order,
                is_active=True,
            )

    if not TransformOperation.objects.exists():
        transform_ops = [
            ("trim", "Trim", "mvp", [], 10),
            ("upper", "Mayúsculas", "mvp", [], 20),
            ("lower", "Minúsculas", "mvp", [], 30),
            ("date_format", "Formato fecha", "mvp", ["format", "input_formats"], 40),
            ("pad_left", "Pad izquierda", "mvp", ["char", "length"], 50),
            ("pad_right", "Pad derecha", "mvp", ["char", "length"], 60),
            ("default_if_empty", "Default si vacío", "mvp", ["value"], 70),
            ("replace_map", "Mapa de códigos", "phase_2", ["map"], 80),
            ("replace", "Reemplazar texto", "phase_2", ["find", "replace", "regex"], 90),
            ("substring", "Substring", "phase_2", ["start", "length"], 100),
            ("ltrim", "Trim izquierda", "phase_2", [], 110),
            ("rtrim", "Trim derecha", "phase_2", [], 120),
            ("regex_extract", "Extraer regex", "phase_2", ["pattern", "group"], 130),
            ("coalesce", "Coalesce", "phase_2", ["value", "values"], 140),
            ("number_format", "Formato numérico", "phase_2", ["decimal_places", "thousands_sep", "decimal_sep"], 150),
            ("boolean_map", "Mapa booleano", "phase_2", ["true_values", "false_values", "output_true", "output_false"], 160),
        ]
        for code, name, phase, params, order in transform_ops:
            TransformOperation.objects.create(
                code=code,
                name=name,
                description="",
                resolver_key=code,
                param_schema=params,
                phase=phase,
                sort_order=order,
                is_active=True,
            )


def unseed_packages_and_ops(apps, schema_editor):
    PermissionPackage = apps.get_model("dms", "PermissionPackage")
    TransformOperation = apps.get_model("dms", "TransformOperation")
    PermissionPackage.objects.all().delete()
    TransformOperation.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("dms", "0010_permission_and_transform_catalogs"),
    ]

    operations = [
        migrations.RunPython(seed_packages_and_ops, unseed_packages_and_ops),
    ]
