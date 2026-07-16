"""Datos semilla para catálogos DMS (system_catalogs.md)."""


def seed_catalogs(apps, schema_editor):
    SourceFileType = apps.get_model("dms", "SourceFileType")
    TargetFileType = apps.get_model("dms", "TargetFileType")
    CharsetEncoding = apps.get_model("dms", "CharsetEncoding")
    LineEnding = apps.get_model("dms", "LineEnding")
    FieldContentType = apps.get_model("dms", "FieldContentType")
    CaptureBoundaryMode = apps.get_model("dms", "CaptureBoundaryMode")
    TargetFieldDataType = apps.get_model("dms", "TargetFieldDataType")
    ExecutionErrorCode = apps.get_model("dms", "ExecutionErrorCode")
    FilenamePatternVariable = apps.get_model("dms", "FilenamePatternVariable")
    ValueGeneratorType = apps.get_model("dms", "ValueGeneratorType")
    PermissionPackage = apps.get_model("dms", "PermissionPackage")
    TransformOperation = apps.get_model("dms", "TransformOperation")
    TransformPipelineTemplate = apps.get_model("dms", "TransformPipelineTemplate")

    if SourceFileType.objects.exists():
        return

    source_types = [
        ("txt_fixed", "TXT posicional", [".txt"], "txt_fixed", "mvp", 10),
        ("txt_delimited", "TXT delimitado", [".txt"], "txt_delimited", "mvp", 20),
        ("csv", "CSV", [".csv"], "csv", "mvp", 30),
        ("xlsx", "Excel", [".xlsx", ".xls"], "xlsx", "mvp", 40),
        ("json", "JSON", [".json"], "json", "mvp", 50),
        ("xml", "XML", [".xml"], "xml", "mvp", 60),
    ]
    for code, name, ext, parser, phase, order in source_types:
        SourceFileType.objects.create(
            code=code,
            name=name,
            extensions=ext,
            parser_key=parser,
            phase=phase,
            sort_order=order,
            is_active=True,
        )

    target_types = [
        ("txt_fixed", "TXT posicional", [".txt"], "txt_fixed", "mvp", 10),
        ("txt_delimited", "TXT delimitado", [".txt"], "txt_delimited", "mvp", 20),
        ("csv", "CSV", [".csv"], "csv", "mvp", 30),
        ("xlsx", "Excel", [".xlsx"], "xlsx", "mvp", 40),
        ("json", "JSON", [".json"], "json", "mvp", 50),
        ("xml", "XML", [".xml"], "xml", "mvp", 60),
    ]
    for code, name, ext, serializer, phase, order in target_types:
        TargetFileType.objects.create(
            code=code,
            name=name,
            extensions=ext,
            serializer_key=serializer,
            phase=phase,
            sort_order=order,
            is_active=True,
        )

    encodings = [
        ("auto", "Detección automática", "", True, 0),
        ("utf-8", "UTF-8", "utf-8", False, 10),
        ("latin-1", "Latin-1 (ISO-8859-1)", "latin-1", False, 20),
        ("windows-1252", "Windows-1252", "cp1252", False, 30),
    ]
    for code, name, charset, auto, order in encodings:
        CharsetEncoding.objects.create(
            code=code,
            name=name,
            charset_value=charset,
            is_auto_detect=auto,
            sort_order=order,
            is_active=True,
        )

    line_endings = [
        ("auto", "Detección automática", "", True, False, 0),
        ("lf", "LF (Unix)", r"\n", False, False, 10),
        ("crlf", "CRLF (Windows)", r"\r\n", False, False, 20),
        ("custom", "Personalizado", "", False, True, 30),
    ]
    for code, name, seq, auto, custom, order in line_endings:
        LineEnding.objects.create(
            code=code,
            name=name,
            sequence=seq,
            is_auto_detect=auto,
            allows_custom_value=custom,
            sort_order=order,
            is_active=True,
        )

    content_types = [
        ("alphanumeric", "Alfanumérico", r"^[A-Za-z0-9]+$", False, False, "mvp", 10),
        ("alpha", "Solo letras", r"^[A-Za-z]+$", False, False, "mvp", 20),
        ("numeric", "Solo números", r"^[0-9]+$", False, False, "mvp", 30),
        ("decimal", "Decimal", r"^[0-9]+(\.[0-9]+)?$", False, False, "mvp", 40),
        ("alphanumeric_spaces", "Alfanumérico con espacios", r"^[A-Za-z0-9 ]+$", False, False, "mvp", 50),
        ("date", "Fecha", "", True, False, "mvp", 60),
        ("datetime", "Fecha y hora", "", True, False, "mvp", 70),
        ("free_text", "Texto libre", "", False, False, "mvp", 80),
        ("custom", "Patrón propio", "", False, True, "mvp", 90),
    ]
    for code, name, pattern, req_date, custom, phase, order in content_types:
        FieldContentType.objects.create(
            code=code,
            name=name,
            default_pattern=pattern,
            requires_date_format=req_date,
            allows_custom_pattern=custom,
            phase=phase,
            sort_order=order,
            is_active=True,
        )

    boundary_modes = [
        ("first", "Primera línea", "start", None, "mvp", 10),
        ("line_number", "Línea específica", "both", {"line": "integer"}, "mvp", 20),
        ("after_header_block", "Tras N líneas iniciales", "start", {"skip_lines": "integer"}, "mvp", 30),
        ("after_pattern", "Tras patrón regex", "start", {"pattern": "string"}, "mvp", 40),
        ("after_blank_run", "Tras líneas en blanco", "start", {"blank_count": "integer"}, "mvp", 50),
        ("marker_start", "Marcador de inicio", "start", {"marker": "string"}, "mvp", 60),
        ("eof", "Final del archivo", "end", None, "mvp", 70),
        ("percent", "Porcentaje del archivo", "end", {"value": "number"}, "mvp", 80),
        ("max_rows", "Máximo de filas", "end", {"max_rows": "integer"}, "mvp", 90),
        ("before_pattern", "Antes de patrón", "end", {"pattern": "string"}, "mvp", 100),
        ("marker_end", "Marcador de fin", "end", {"marker": "string"}, "mvp", 110),
        ("blank_run", "Líneas en blanco consecutivas", "end", {"blank_count": "integer"}, "mvp", 120),
        ("line_or_eof", "Línea N o EOF", "end", {"line": "integer"}, "mvp", 130),
    ]
    for code, name, applies, schema, phase, order in boundary_modes:
        CaptureBoundaryMode.objects.create(
            code=code,
            name=name,
            applies_to=applies,
            param_schema=schema,
            phase=phase,
            sort_order=order,
            is_active=True,
        )

    target_data_types = [
        ("string", "Texto", False, "text", ["alphanumeric", "alpha", "free_text", "alphanumeric_spaces"], "mvp", 10),
        ("integer", "Entero", False, "number", ["numeric"], "mvp", 20),
        ("decimal", "Decimal", False, "number", ["decimal", "numeric"], "mvp", 30),
        ("date", "Fecha", True, "date", ["date"], "mvp", 40),
        ("datetime", "Fecha y hora", True, "date", ["datetime", "date"], "mvp", 50),
        ("boolean", "Sí/No", False, "general", [], "mvp", 60),
    ]
    for code, name, req_fmt, excel, suggested, phase, order in target_data_types:
        TargetFieldDataType.objects.create(
            code=code,
            name=name,
            requires_format=req_fmt,
            excel_type=excel,
            suggested_content_types=suggested,
            phase=phase,
            sort_order=order,
            is_active=True,
        )

    error_codes = [
        (
            "CONTENT_TYPE_MISMATCH",
            "Tipo de contenido inválido",
            "Valor no cumple el tipo de contenido esperado{detail}.",
            "parse",
            "error",
            10,
        ),
        (
            "REQUIRED_FIELD_EMPTY",
            "Campo obligatorio vacío",
            "Campo obligatorio vacío{detail}.",
            "parse",
            "error",
            20,
        ),
        (
            "PATTERN_MISMATCH",
            "No cumple patrón",
            "No cumple el patrón esperado{detail}.",
            "parse",
            "error",
            30,
        ),
        (
            "FORBIDDEN_CHAR",
            "Carácter prohibido",
            "La línea contiene un carácter prohibido{detail}.",
            "parse",
            "error",
            40,
        ),
        (
            "FORBIDDEN_PATTERN",
            "Patrón prohibido",
            "La línea coincide con un patrón prohibido{detail}.",
            "parse",
            "error",
            45,
        ),
        (
            "LINE_LENGTH_MISMATCH",
            "Línea más corta que lo definido",
            "Línea más corta que la definición posicional{detail}.",
            "parse",
            "error",
            50,
        ),
        (
            "DELIMITER_MISMATCH",
            "Columnas inconsistentes",
            "Columnas inconsistentes{detail}.",
            "parse",
            "error",
            60,
        ),
        (
            "CAPTURE_OUT_OF_RANGE",
            "Línea fuera de rango captura",
            (
                "El archivo tiene {actual_lines} línea(s); "
                "la captura pedía hasta {expected_line}. "
                "Se procesó hasta el final disponible."
            ),
            "parse",
            "warning",
            70,
        ),
        (
            "TARGET_REQUIRED_EMPTY",
            "Campo destino obligatorio vacío",
            "Campo destino obligatorio vacío{detail}.",
            "write",
            "error",
            80,
        ),
        (
            "TARGET_TYPE_MISMATCH",
            "Tipo destino incompatible",
            "Tipo destino incompatible{detail}.",
            "write",
            "error",
            90,
        ),
        (
            "TARGET_LENGTH_EXCEEDED",
            "Supera longitud máxima",
            "Supera la longitud máxima{detail}.",
            "write",
            "error",
            100,
        ),
        (
            "TARGET_RECORD_LENGTH_OVERFLOW",
            "Línea excede longitud registro",
            "La línea excede la longitud del registro{detail}.",
            "write",
            "error",
            110,
        ),
        (
            "TARGET_PATTERN_MISMATCH",
            "No cumple patrón destino",
            "No cumple el patrón destino{detail}.",
            "write",
            "error",
            120,
        ),
        (
            "TARGET_SERIALIZATION_ERROR",
            "Error al formatear valor",
            "Error al formatear el valor{detail}.",
            "write",
            "error",
            130,
        ),
        (
            "JOB_ABORTED",
            "Ejecución abortada por política",
            "Ejecución abortada por política.",
            "job",
            "error",
            140,
        ),
        (
            "JOB_STORAGE_ERROR",
            "Error de almacenamiento",
            "Error de almacenamiento.",
            "job",
            "error",
            150,
        ),
        (
            "JOB_INVALID_OUTPUT_PATTERN",
            "Patrón de nombre salida inválido",
            "Patrón de nombre de salida inválido.",
            "job",
            "error",
            160,
        ),
    ]
    for code, name, description, phase, severity, order in error_codes:
        ExecutionErrorCode.objects.create(
            code=code,
            name=name,
            description=description,
            phase=phase,
            severity=severity,
            sort_order=order,
            is_active=True,
        )

    filename_vars = [
        ("project", "{project}", "nomina-sap", "project.name_short", False, 10),
        ("project_name", "{project_name}", "Nomina_SAP", "project.name_sanitized", False, 20),
        ("date", "{date}", "20250712", "job.finished_at.date", False, 30),
        ("date_formatted", "{date:%Y%m%d}", "20250712", "job.finished_at.strftime", True, 40),
        ("datetime", "{datetime}", "20250712T091430", "job.finished_at.iso", False, 50),
        ("job_id", "{job_id}", "a1b2c3d4", "job.id_short", False, 60),
        ("version", "{version}", "2", "project_version.number", False, 70),
        ("ext", "{ext}", ".csv", "target_file_type.extension", False, 80),
    ]
    for code, syntax, example, resolver, supports_fmt, order in filename_vars:
        FilenamePatternVariable.objects.create(
            code=code,
            name=code.replace("_", " ").title(),
            syntax=syntax,
            example_value=example,
            resolver_key=resolver,
            supports_format=supports_fmt,
            sort_order=order,
            is_active=True,
        )

    generators = [
        ("sequence_numeric", "Secuencia numérica", "sequence_numeric", 10),
        ("sequence_padded", "Secuencia con padding", "sequence_padded", 20),
        ("sequence_alphanumeric", "Secuencia alfanumérica", "sequence_alphanumeric", 30),
        ("sequence_template", "Plantilla con secuencia", "sequence_template", 40),
        ("unique_uuid", "UUID por fila", "unique_uuid", 50),
        ("unique_job_counter", "Correlativo por job", "unique_job_counter", 60),
        ("job_timestamp", "Fecha/hora de ejecución", "job_timestamp", 70),
        ("row_number", "Número de fila", "row_number", 80),
    ]
    for code, name, resolver, order in generators:
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


def unseed_catalogs(apps, schema_editor):
    for model_name in (
        "SourceFileType",
        "TargetFileType",
        "CharsetEncoding",
        "LineEnding",
        "FieldContentType",
        "CaptureBoundaryMode",
        "TargetFieldDataType",
        "ExecutionErrorCode",
        "FilenamePatternVariable",
        "ValueGeneratorType",
        "PermissionPackage",
        "TransformOperation",
        "TransformPipelineTemplate",
    ):
        apps.get_model("dms", model_name).objects.all().delete()
