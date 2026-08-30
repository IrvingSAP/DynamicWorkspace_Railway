# Módulo 2 — Contrato común (PLATFORM API)

Forma de request/response, `wait`, `kind`, estados y errores tipados.

> **Estado:** **implementado** (`contract_service`, `GET /api/v1/contract`, `POST /api/v1/jobs/validate`, UI US)  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §5 · §5.5 · §8 · §9  
> **Fase:** A (base de M3–M6)  
> **No ejecuta jobs:** el run queda en [`pa_jobs_run.md`](pa_jobs_run.md)

---

## Propósito

Un **solo patrón HTTP** para todos los `kind` ejecutables. El shape de archivos y `summary` varía por app; `ok`, `status`, `errors[]`, `job_id` y `artifacts` no.

---

## Qué hay en código

| Pieza | Dónde |
|-------|--------|
| Catálogo, parseo, envelope | `apps.platform_api.services.contract_service` |
| Catálogo HTTP | `GET /api/v1/contract` (Bearer) |
| Validar metadatos (sin runner) | `POST /api/v1/jobs/validate` |
| UI US | `/app/platform-api/contrato/` |

---

## Dos ejes (no mezclar)

| Eje | Valores | Significado |
|-----|---------|-------------|
| **Qué** | `kind` + `project_slug` **o** `kind=file_pipeline` + `pipeline_id` | Job suelto vs cadena |
| **Espera HTTP** | `wait=sync` \| `async` | 200 al terminar vs 202 + polling |

Atajo: `mode=pipeline` ≡ `kind=file_pipeline`. Default de pipeline: `wait=async` → HTTP 202 en el run futuro.

---

## Decisiones de envelope

| Tema | Decisión |
|------|----------|
| Rechazo de negocio (Gate) | HTTP **200** + `ok: false` + `status: completed` + `summary.verdict` `accepted`\|`rejected` |
| Request inválido | 400 + `errors[]` (`row`, `field`, `code`, `message`) |
| Sin publicada / pipeline no active | 409 (se aplica en M3) |
| `accepted` | Solo veredicto Gate; **nunca** status de pipeline run |
| Fase A / B / C cableado | `file_gate`, `dms`, `reverse`, `file_match`, `structure_scout`, `file_clean`, `file_split`, `file_merge` y `file_pipeline` ejecutables; el resto está en el catálogo |

Kinds canónicos: `file_gate`, `dms`, `reverse`, `file_match`, `structure_scout`, `file_clean`, `file_split`, `file_merge`, `file_repair`, `data_profiler`, `file_pipeline`.

---

## Relacionados

[`pa_jobs_run.md`](pa_jobs_run.md) · [`pa_pipeline.md`](pa_pipeline.md) · [`pa_openapi.md`](pa_openapi.md) · [`../PLATFORM_API.md`](../PLATFORM_API.md) §5 · [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) §3.17
