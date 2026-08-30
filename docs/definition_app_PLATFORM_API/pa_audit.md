# Módulo 7 — Auditoría API y tablero (PLATFORM API)

Plano HTTP/máquina del disparo. Paridad con historial UI y pulso del dashboard.

> **Estado:** implementado  
> **Distinto de:** [`pa_client_audit.md`](pa_client_audit.md) — trazabilidad del **cliente/key**, no del job.  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §10.2 · §10.3  
> **Hereda:** [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §7.1 (definición + paso — **no copiar**)  
> **Fase:** A (campos en el job); tablero en Pipeline UI (`pipeline_dashboard_service`)

---

## Propósito

Todo job o pipeline run vía API deja rastro de **quién (máquina)**, **cuándo**, **qué versión** y **hashes**. El operador humano ve el mismo hecho en historial / detalle. El tablero de Pipeline **cuenta** esos runs (`trigger_source=api`).

---

## Alcance

| Sí | No |
|----|-----|
| Campos de disparo API en el persistido | Auditar diseño de esquemas o editor de pipeline |
| `GET` de esos metadatos (`jobs:read`) | API de métricas que sustituya el tablero (MVP) |
| Dry-run marcado y excluido del pulso | Borrar auditoría (append-only; soft-delete = política PA/UI) |

---

## Implementación

| Pieza | Dónde |
|-------|--------|
| Stamp job (`input_suggestions`) | `job_audit_service.stamp_job_suggestions` + `job_run_service._stamp_api` |
| Persistencia pipeline | `PipelineRun.trigger_source`, `api_client_id`, `correlation_id`, `idempotency_key`, `client_ip`, `user_agent`, `dry_run` |
| Envelope GET / POST | `audit` vía `job_audit_payload` / `pipeline_audit_payload` |
| Correlation si falta header | `ensure_correlation_id` en `run_job` |
| IP / UA | `posted_from_request` (META + `X-Forwarded-For`) |
| Pulso tablero | `ops = window_runs.filter(dry_run=False)`; fallos, recientes y último run por pipeline usan `ops` |

---

## Campos mínimos (disparo API)

| Campo | Uso |
|-------|-----|
| `trigger_source` | Siempre `api` |
| `triggered_by_api_client_id` | Cliente OAuth / key |
| `idempotency_key` | Si vino en el request |
| `correlation_id` | Traza cliente ↔ API ↔ runner ↔ pasos (se genera si no hay header) |
| `job_id` · `pipeline_run_id` | Mismos ids en UI |
| `app_job_id` | Por paso (solo pipeline; también en `steps[]`) |
| `client_ip` / `user_agent` | Desde META |
| Hashes entrada / artifacts | Evidencia; no contenido (`input_hash` / `content_hash`) |
| `triggered_at` · `started_at` · `finished_at` · `duration_ms` | Timing |
| `dry_run` | Flag |

---

## Dashboard

Tablero: [`../definition_app_FILE_PIPELINE/pipeline_dashboard.md`](../definition_app_FILE_PIPELINE/pipeline_dashboard.md) (`/app/file-pipeline/tablero/`).

| Decisión | |
|----------|--|
| ¿La API sustituye el tablero? | No |
| ¿Runs API alimentan el pulso? | **Sí** (excepto `dry_run`) |
| ¿`GET /api/v1/ops/summary`? | No en MVP; misma visibilidad que el tablero si se añade |

Jobs sueltos (Gate/Pipe sin pipeline) → historial de **esa app**, no el tablero de pipelines (salvo tablero de plataforma futuro).

---

## Criterio de aceptación

1. `trigger_source=api` en persistencia (job `input_suggestions` o `PipelineRun`).  
2. Mismo `job_id` / `pipeline_run_id` en GET y en UI.  
3. Dry-run fuera del pulso (`dry_run=False` en métricas y último run).  
4. Pipeline §7.1 referenciado, no duplicado.

---

## Relacionados

[`pa_jobs_query.md`](pa_jobs_query.md) · [`pa_pipeline.md`](pa_pipeline.md) · [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §7.1
