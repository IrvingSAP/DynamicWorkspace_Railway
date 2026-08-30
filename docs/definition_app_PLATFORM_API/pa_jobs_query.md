# Módulo 4 — Consulta y artifacts (PLATFORM API)

Leer estado del job y descargar informe / salida con TTL.

> **Estado:** **implementado** (`job_query_service`, `GET /api/v1/jobs`, `GET /jobs/{id}`, report/output)  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §10.1  
> **Fase:** A (detalle + descarga) y listado básico · **query multi-app** (Match, Scout, Clean, Split/Merge, Pipeline)  
> **Depende:** [`pa_auth.md`](pa_auth.md) scopes `jobs:read` · `artifacts:download`

---

## Propósito

El cliente correlaciona por `job_id`: estado, auditoría de disparo y links a artifacts.

Las mismas rutas resuelven **todos** los kinds cableados: `DmsExecutionJob` (Gate / FilePipe / Reverse), `FileMatchJob`, `ScoutDetectionState`, `CleanJob`, `SplitMergeJob` y `PipelineRun`. El `kind` del envelope distingue split vs merge (`operation`). Structure Scout no genera bytes de informe/salida (404).

Listado sin `kind`: unión paginada por `created_at`. Con `kind`, solo esa fuente. `file_split` / `file_merge` filtran la misma tabla por operación.

---

## Endpoints

| Acción | Método | Ruta | Scope |
|--------|--------|------|--------|
| Listado | GET | `/api/v1/jobs` | `jobs:read` |
| Detalle | GET | `/api/v1/jobs/{id}` | `jobs:read` |
| Informe | GET | `/api/v1/jobs/{id}/report` | `artifacts:download` **o** `?token=` firmado |
| Salida | GET | `/api/v1/jobs/{id}/output` | igual (vacío en Gate → 404) |

Listado: filtros `kind`, `status`, `api_client_id`, `created_from`, `created_to`, `limit`, `offset`. Solo la compañía del token.

Job ajeno o inexistente: **404 opaco**.

TTL: política de compañía (`artifact_ttl_hours`). El token firmado caduca con ese TTL.

Sin `artifacts:download` se puede leer metadatos (`jobs:read`); los bytes exigen scope o token.

---

## Relacionados

[`pa_jobs_run.md`](pa_jobs_run.md) · [`pa_audit.md`](pa_audit.md) · [`pa_contract.md`](pa_contract.md)
