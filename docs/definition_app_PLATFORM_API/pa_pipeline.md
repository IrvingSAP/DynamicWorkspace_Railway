# Módulo 6 — kind=file_pipeline (PLATFORM API)

Disparo HTTP de un pipeline publicado. La API **delega**; no orquesta.

> **Estado:** implementado (`apps.platform_api`)  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §5.4  
> **Orquestador:** [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §3 · §7 · **§7.1** (no duplicar)

---

## Propósito

Un cliente externo envía archivo(s) + `pipeline_id` (definición **active** + versión publicada). El orquestador (`pipeline_run_service.start_run`) ejecuta la cadena. La API expone `pipeline_run_id` + `steps[]`.

---

## Alcance

| Sí | No |
|----|-----|
| `kind=file_pipeline` en `POST /api/v1/jobs/run` | Diseñar / publicar pasos por HTTP |
| Atajo `POST /api/v1/pipelines/{pipeline_id}/runs` | Reimplementar handoff o runners |
| Scope `pipeline:run` + permiso en **cada** proyecto de paso | Fan-out Split (fase 2 del Pipeline) |

`trigger_source=api` en `PipelineRun`. Auditoría E2E de definición y paso: **solo** FILE_PIPELINE §7.1.

---

## Contrato

```http
POST /api/v1/jobs/run
Authorization: Bearer …
Idempotency-Key: …
Content-Type: multipart/form-data

kind=file_pipeline
pipeline_id=nomina-diaria
version=published
wait=async
file=<bytes>
```

Equivalente: `POST /api/v1/pipelines/{pipeline_id}/runs`.

Default: `wait=async`. HTTP 202 solo si el run queda `queued`/`running`; si el orquestador termina en el mismo request, 200 con `ok` y `steps[]`.

Polling: `GET /api/v1/jobs/{id}` (el id es el `pipeline_run_id`). Listado: `GET /api/v1/jobs?kind=file_pipeline`.

---

## Rechazo

- Definición no `active` o sin versión publicada → **409** `unpublished`.
- Cliente sin `pipeline:run` → **403**.
- Actor sin ejecutar algún proyecto de paso → **403**.
- Pipeline de otra compañía → **404** opaco.

La máquina **no** bypasea tenancy ni permisos de los proyectos destino. Sí omite membresía de pipeline (el scope de máquina sustituye el rol PA/ED/GE).

---

## Criterio de aceptación

1. Un solo orquestador (UI y API): `start_run`.  
2. §7.1 del Pipeline no copiado aquí.  
3. Denegación si falta permiso en un paso.

---

## Relacionados

[`pa_contract.md`](pa_contract.md) · [`pa_audit.md`](pa_audit.md) · [`../definition_app_FILE_PIPELINE/`](../definition_app_FILE_PIPELINE/)
