# Módulo 3 — POST /jobs/run (PLATFORM API)

Disparo sync de job suelto. Cableados: File Gate, FilePipe, Reverse Studio, File Match, Structure Scout, File Clean, File Split y File Merge.

> **Estado:** **implementado** (`job_run_service`, `POST /api/v1/jobs/run`)  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §5 · §7 · §14 Fase A (Gate/Pipe) · Fase B (Reverse, Match, Scout) · Fase C (Clean, Split, Merge)  
> **Fase:** A + B + C (Clean/Split/Merge)  
> **Depende:** [`pa_auth.md`](pa_auth.md) · [`pa_contract.md`](pa_contract.md)

---

## Propósito

`POST /api/v1/jobs/run` ejecuta la **versión publicada** del proyecto con el **mismo runner** que la UI. Respuesta sync (`wait=sync`) con envelope común.

---

## Alcance actual

| Sí | No (aún) |
|----|----------|
| `kind=file_gate` · `kind=dms` · `kind=reverse` · `kind=file_match` · `kind=structure_scout` · `kind=file_clean` · `kind=file_split` · `kind=file_merge` | Repair (app no instalada) |
| `kind=file_pipeline` (delega) | — |
| `wait=sync` (async encola; Match, Scout, Clean, Split y Merge solo sync) | — |
| Scope `jobs:run` | — |

Reverse reusa el runner DMS (`upload_production` + `run_full_job`) sobre un proyecto `project_kind=reverse`.

Match llama `match_and_run` con `file_a` y `file_b` sobre un proyecto `project_kind=file_match`.

Scout sube la muestra (`upload_sample`) y reejecuta detección (`rerun_detection`) sobre `project_kind=structure_scout`. El `job_id` es el id de la detección, no un job productivo. `wait=async` no está soportado.

Clean llama `run_clean_job` con un archivo sobre `project_kind=file_clean`. Admite `dry_run`. `wait=async` no está soportado.

Split/Merge llaman `run_sm_job` sobre `project_kind=file_split_merge`. `file_split` exige un `file` y operación publicada split; `file_merge` exige `files` (mín. 2) y operación merge. `wait=async` no está soportado.

---

## Flujo

```text
Bearer + jobs:run + rate limit + política de archivo
  → Proyecto de la compañía (slug) y kind coincidente
  → Versión publicada (409 si falta; Scout no exige versión publicada)
  → Runner UI: validate_and_run / upload_production + run_full_job / match_and_run / upload_sample + rerun_detection / run_clean_job / run_sm_job
  → trigger_source=api
  → 200 + envelope
```

La membresía humana se omite: el cliente de máquina de la compañía actúa como servicio.

---

## Relacionados

[`pa_contract.md`](pa_contract.md) · [`pa_jobs_query.md`](pa_jobs_query.md) · [`pa_audit.md`](pa_audit.md) · [`../FILE_GATE.md`](../FILE_GATE.md)
