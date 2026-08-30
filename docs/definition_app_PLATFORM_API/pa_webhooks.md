# Módulo 8 — Webhooks (PLATFORM API)

Notificación al callback del cliente cuando el job/run termina.

> **Estado:** implementado (`apps.platform_api.services.webhook_service`)  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §10.1 Fase C · §4.2  
> **Fase:** C (Pipeline puede alinearlo en su Fase B de disparadores)

---

## Propósito

Evitar solo polling: el sistema hace `POST` a una URL registrada del cliente con el resultado. Complemento de [`pa_jobs_query.md`](pa_jobs_query.md), no su reemplazo.

---

## Implementación

| Pieza | Dónde |
|-------|--------|
| Config por cliente | `ApiClient.webhook_*` + ficha US |
| Allowlist de host | Política de proceso (HTTPS, anti-SSRF) |
| Firma | `X-Platform-Signature: sha256=…` HMAC del body; secreto nunca en query |
| Entregas / reintentos | `ApiWebhookDelivery` · backoff 15s / 1m / 5m / 15m · máx. 5 |
| Disparo | Tras `run_job` / pipeline terminal y tras `cancel_job` |
| Payload | ids, `kind`, `status`, `ok`, `correlation_id`, `links` — sin archivo ni celdas |

Eventos: `job.completed` · `job.failed` · `job.cancelled` (también en corridas de pipeline; `pipeline_run_id` en el cuerpo).

`GET /api/v1/jobs/{id}` sigue siendo válido sin webhook.

---

## Relacionados

[`pa_auth.md`](pa_auth.md) · [`pa_security.md`](pa_security.md) · [`pa_jobs_query.md`](pa_jobs_query.md) · [`pa_openapi.md`](pa_openapi.md)
