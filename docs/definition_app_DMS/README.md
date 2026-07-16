# definition_app_DMS — Definición Data Mapping Studio

Carpeta de documentación de análisis y definición para **Data Mapping Studio (DMS)**, módulo ETL acoplado a **DynamicWorkspace**.

> **Integración:** DMS reutiliza `Company`, `UserProfile`, `Project`, `ProjectMembership`, seguridad y billing existentes. Ver [`dms_integration.md`](dms_integration.md).

---

## Documentos

| Archivo | Contenido |
|---------|-----------|
| [`dms_integration.md`](dms_integration.md) | **Alineación con DynamicWorkspace** — modelos, roles, tenant, URLs |
| [`../DataMappingStudio.md`](../DataMappingStudio.md) | Visión inicial DMS (análisis autónomo) |
| [`../DynamicWorkspace.md`](../DynamicWorkspace.md) | Plataforma base — compañías, usuarios, proyectos workspace |
| [`../definition_app/DynamicWorkspace_Model.md`](../definition_app/DynamicWorkspace_Model.md) | Modelos Django existentes + índice DMS |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Mensajes UI (incl. §3.8 origen / destino / mapeo) |
| [`source_definition.md`](source_definition.md) | Módulo 1: definición de origen — asistente 6 pasos, `SourceProfile` |
| [`system_catalogs.md`](system_catalogs.md) | Tablas de sistema — catálogos con listado y CRUD (admin UA) |
| [`target_definition.md`](target_definition.md) | Módulo 4: definición de destino — asistente 6 pasos, `TargetProfile` |
| [`field_mapping.md`](field_mapping.md) | Módulo 2: enlace origen ↔ destino, generadores |
| [`transform_rules.md`](transform_rules.md) | Módulo 3: catálogo y pipeline de transformación post-mapeo |
| [`project_lifecycle.md`](project_lifecycle.md) | Ciclo del proyecto DMS, visibilidad, permisos y flujo |
| [`file_intake.md`](file_intake.md) | Carga de archivos — browse, muestra y producción |
| [`transform_execution.md`](transform_execution.md) | Fase C — ejecución, salida, descarga e historial |

---

## Convención

- Un documento por tema o módulo (`<tema>.md`).
- Nombres en minúsculas con guión bajo si hace falta.
- Los modelos conceptuales de cada doc se implementan en **`apps.dms`** salvo `Project` / `ProjectMembership` (**`apps.projects`**).
- Toda referencia a «organización» o «tenant» = **`Company`** (`apps.company`).
- Mensajes de operación: [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md).

---

## Índice y estado

| Documento | Estado |
|-----------|--------|
| Integración DynamicWorkspace | [`dms_integration.md`](dms_integration.md) — en revisión · modelos parciales en código |
| Definición general | Ver `DataMappingStudio.md` + `DynamicWorkspace.md` |
| Project lifecycle | [`project_lifecycle.md`](project_lifecycle.md) — en revisión · hub/mapping parcial |
| **Source definition** | [`source_definition.md`](source_definition.md) — **MVP** (wizard 1–6, JSON/XML, captura patrón/blancos, B+E) |
| **Target definition** | [`target_definition.md`](target_definition.md) — **MVP implementado** (wizard 1–6) |
| **Field mapping** | [`field_mapping.md`](field_mapping.md) — **MVP implementado** (editor + persistencia + publicar) |
| **Transform rules** | [`transform_rules.md`](transform_rules.md) — **MVP implementado** (hub + editor + preview + `apply_pipeline`) |
| System catalogs | [`system_catalogs.md`](system_catalogs.md) — mantenimiento + semillas (incl. `PermissionPackage`, `TransformOperation`, `ValueGeneratorType`) |
| Transform execution | [`transform_execution.md`](transform_execution.md) — **MVP** (parsers, informe localizado, dry-run, job, descarga, historial) |
| File intake | [`file_intake.md`](file_intake.md) — **MVP implementado** (muestra + producción upload) |
| UI / prototipos | Prototipos en `prototype/dms/`; UI app en `templates/dms/` |
