# PLATFORM API — Integración transversal

Kind, runners, URLs, mapeo UI↔API. Inventario cableado al código.

> **Archivo:** `pa_integration.md`  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §3 · §12  
> **Estado:** implementado (`integration_service`, `GET /api/v1/integration`, guía US)

---

## 1. Identidad y chasis

| Ítem | Valor |
|------|--------|
| Código producto | `PLATFORM_API` |
| Label | API de jobs / ejecución remota |
| App Django | `apps.platform_api` (**no** `project_kind`) |
| Prefijo HTTP | `/api/v1/` |
| Sidebar UF | **No** |
| UI US | Clientes/keys + contrato, paths, integración, seguridad, auditoría |

---

## 2. Qué reusa / qué no

| Reusa | No reusa |
|-------|----------|
| `validate_and_run` / `run_full_job` / `start_run` (y runners de cada app) | Parsers, reglas, diseñadores |
| Orquestador File Pipeline | Un segundo motor de cadena |
| `UI_MESSAGES` / `error_code` | Django Forms |
| Storage / TTL de jobs existentes | Historial paralelo no enlazado |
| `Company` + billing/flags | Tenant propio |

---

## 3. Runners por kind (inventario)

Fuente de verdad: `apps.platform_api.services.integration_service` y `GET /api/v1/integration`.

| `kind` | App | Runner | Fase | Cableado en `POST /jobs/run` |
|--------|-----|--------|------|------------------------------|
| `file_gate` | File Gate | `validation_run_service.validate_and_run` | A | Sí |
| `dms` | FilePipe | `execution_service.run_full_job` | A | Sí |
| `reverse` | Reverse Studio | mismo `run_full_job` DMS | B | Sí |
| `file_match` | File Match | `match_run_service.match_and_run` | B | Sí (`file_a` + `file_b`, solo sync) |
| `structure_scout` | Structure Scout | `detect_pattern_service.rerun_detection` | B | Sí (muestra + detección, solo sync) |
| `file_clean` | File Clean | `clean_run_service.run_clean_job` | C | Sí (un archivo, solo sync, `dry_run`) |
| `file_split` | File Split/Merge | `sm_run_service.run_sm_job` | C | Sí (un archivo, solo sync) |
| `file_merge` | File Split/Merge | `sm_run_service.run_sm_job` | C | Sí (`files` ≥ 2, solo sync) |
| `file_repair` | File Repair | — (app no instalada) | C | No |
| `data_profiler` | Data Profiler | — (app no instalada) | C | No |
| `file_pipeline` | File Pipeline | `pipeline_run_service.start_run` | B | Sí (delega) |

`workspace` (Worksheets): **fuera** de esta API de archivos.

Watch / Scheduler: mismo runner; `trigger_source` distinto. Archive: custodia de `job_id` / `pipeline_run_id` — no bloquea MVP.

---

## 4. Mapeo UI ↔ API

| UI | API |
|----|-----|
| Ejecutar proyecto publicado | `POST /jobs/run` + `kind` + `project_slug` |
| Ejecutar pipeline publicado | `kind=file_pipeline` (o atajo `/pipelines/{id}/runs`) |
| Historial de la app | Mismo `job_id` (tabla de esa app). `GET /jobs/{id}` lo resuelve sin path por kind |
| Detalle / auditoría pipeline | Mismo `pipeline_run_id` · [`pa_audit.md`](pa_audit.md) |
| Tablero Pipeline | Pulso incluye `trigger_source=api` |
| GE en proyecto | Scope run + membresía/servicio |

Un solo path de ejecución: `POST /api/v1/jobs/run`.

---

## 5. Settings / INSTALLED_APPS

`apps.platform_api` en `INSTALLED_APPS`. UI US: `/app/platform-api/clientes/` e `/app/platform-api/integracion/`. HTTP: `GET /api/v1/whoami`, `GET /api/v1/integration`.

Paths: [`pa_openapi.md`](pa_openapi.md).

---

## Relacionados

[`README.md`](README.md) · [`../APP_FACTORY.md`](../APP_FACTORY.md) · [`../definition_app_FILE_PIPELINE/fp_integration.md`](../definition_app_FILE_PIPELINE/fp_integration.md)
