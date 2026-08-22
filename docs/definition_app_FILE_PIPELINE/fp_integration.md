# FILE PIPELINE — Integración transversal

> **Archivo:** `fp_integration.md`  
> **Producto:** [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md)  
> **Estado:** M1–M2b cableados (`apps.file_pipeline`, URLs, sidebar UF + Step Catalog UA)

---

## 1. Identidad y chasis

| Ítem | Valor |
|------|--------|
| Código producto | `FILE_PIPELINE` |
| Label UI | **File Pipeline** |
| App Django | `apps.file_pipeline` |
| Namespace URLs | `file_pipeline:` |
| Prefijo | `/app/file-pipeline/` |
| Contenedor | `PipelineDefinition` + `PipelineMembership` |
| Sidebar UF | Familia Pipeline → File Pipeline (listado + guía) |

---

## 2. Roles

Misma matriz PA / ED / GE / CO que [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §6.  
Sin roles nuevos. Ejecutar exige permiso sobre **cada** proyecto de paso.

---

## 3. Qué reusa / qué no

| Reusa | No reusa |
|-------|----------|
| Runners `run_*_job` de cada app | Parsers / reglas de Clean o Gate |
| Storage / `storage_service` para artifacts del run | Editor de mapeo FilePipe |
| `UI_MESSAGES` / PRG / HTML plano | Django Forms |
| Membresía y visibilidad de proyectos | Historial de cada app como fuente de verdad E2E |

---

## 4. PLATFORM_API / Watch / Scheduler

| Canal | Contrato |
|-------|----------|
| API | `kind=file_pipeline` o `POST …/pipelines/{id}/runs` · `trigger_source=api` |
| Watch | Llegada → `pipeline_id` · `trigger_source=watch` |
| Scheduler | Cron / dependencia → `pipeline_id` · `trigger_source=scheduler` |

Misma autorización que UI: definición `active` + versión publicada + scopes de compañía. No bypassear tenancy.

---

## 5. Settings / INSTALLED_APPS

Pendiente PLATFORM_API / Watch. Dashboard: `/tablero/`. M5: `/pipelines/<slug>/historial/` y `/runs/<id>/auditoria/`. M4: `PipelineRun` + `/pipelines/<slug>/ejecutar/` y `/runs/<id>/`.

---

*Actualizar este archivo al cablear models, urls y sidebar.*
