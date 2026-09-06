# Módulo 9 — OpenAPI y paths canónicos (PLATFORM API)

Índice de superficie HTTP unificada. El YAML OpenAPI 3 sigue aplazado.

> **Estado:** implementado (`openapi_service`, `GET /api/v1/openapi`, guía US)  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §13 · §14 Fase C  
> **Fase:** índice en código; YAML cuando producto lo pida

---

## Propósito

Dejar **paths y métodos canónicos** para no divergir entre módulos. Este doc + `GET /api/v1/openapi` son el índice. No hay un path de run por app.

---

## Alcance

| Sí | No |
|----|-----|
| Lista de paths `/api/v1/…` | Spec OpenAPI 3 YAML en este módulo |
| Versión de API `v1` | SDKs |
| Punteros a módulos dueños | CRUD proyectos / billing |
| `GET /api/v1/ops/summary` documentado | Implementar métricas (C opcional; tablero Pipeline cubre pulso) |

---

## Implementación

| Pieza | Dónde |
|-------|--------|
| Catálogo | `apps.platform_api.services.openapi_service` |
| HTTP máquina | `GET /api/v1/openapi` (Bearer) |
| Guía US | `/app/platform-api/openapi/` |

Auth: `Authorization: Bearer`. Idempotencia: `Idempotency-Key`. Errores: [`pa_contract.md`](pa_contract.md).

Atajo `POST /api/v1/pipelines/{pipeline_id}/runs` ≡ `POST /api/v1/jobs/run` con `kind=file_pipeline`.

`GET /api/v1/jobs/{job_id}` (y report/output) es **un path**: el id es el de la app que ejecutó (DMS, Match, Scout, Clean, Split/Merge o pipeline run), no un identificador extra de PLATFORM API.

---

## Relacionados

[`pa_contract.md`](pa_contract.md) · [`README.md`](README.md) · [`../PLATFORM_API.md`](../PLATFORM_API.md) §10 · §13
