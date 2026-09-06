# Módulo 5 — Idempotencia, dry-run, cancel y reintento (PLATFORM API)

Operación del cliente más allá del primer POST.

> **Estado:** implementado (`apps.platform_api`)  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §10.1 · §11  
> **HTTP:** `Idempotency-Key`, `dry_run`, `wait=async` (202), `POST /api/v1/jobs/{id}/cancel`

---

## Propósito

Evitar lotes duplicados, permitir vista previa sin contaminar el tablero, y abortar corridas encoladas (`wait=async`).

---

## Idempotencia

Header `Idempotency-Key` + mismo hash de entrada (`contenido + kind + project_slug + dry_run + wait`) → **devolver el mismo `job_id`** sin reejecutar.

Persistencia: `ApiIdempotencyRecord` (único por compañía + cliente + key).

| Caso | Comportamiento |
|------|----------------|
| Mismo key, mismo hash, job existente | Replay HTTP de la respuesta guardada |
| Mismo key, **otro** hash | Conflicto 409 |
| Key nueva | Nuevo job |

---

## Dry-run

`dry_run=true` en el POST: Gate sigue el motor de validación; Pipe usa `dry_run_job` (preview, `JOB_PREVIEW`, sin archivo de salida). Flag `dry_run` en `input_suggestions` y en el envelope. No cuenta en el tablero (`dry_run_counts_in_dashboard` permanece en falso).

---

## Async y cancel

`wait=async` → HTTP **202**, `status=queued` (upload + cola; sin worker de ejecución en este módulo). Polling: [`pa_jobs_query.md`](pa_jobs_query.md).

| Acción | Método | Ruta | Scope |
|--------|--------|------|--------|
| Cancelar | POST | `/api/v1/jobs/{id}/cancel` | `jobs:cancel` |

Resultado: `cancelled` + `cancelled_by_api_client_id`. No aplica a jobs ya `completed` / `partial` / `failed` / `cancelled` (409). Pipeline orquestado: módulo 6.

---

## Reintento

**Nuevo** run: nueva `Idempotency-Key`. Campo opcional `retry_of_job_id` (o `retry_of_run_id`) para traza. Reusar la misma key **no** fuerza otra ejecución.

---

## Criterio de aceptación

1. Idempotencia (key + hash) con replay y 409.  
2. Dry-run fuera del tablero (flag persistido).  
3. Async 202 + cancel con `jobs:cancel`.

---

## Relacionados

[`pa_jobs_run.md`](pa_jobs_run.md) · [`pa_jobs_query.md`](pa_jobs_query.md) · [`pa_webhooks.md`](pa_webhooks.md) · [`pa_security.md`](pa_security.md)
