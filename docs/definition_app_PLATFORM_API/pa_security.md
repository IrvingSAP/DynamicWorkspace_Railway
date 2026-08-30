# Módulo 1b — Seguridad de proceso (PLATFORM API)

Integridad de la ejecución remota: datos, cuotas, artifacts, amenazas HTTP.

> **Estado:** **implementado** (`ApiProcessPolicy`, `process_security_service`, UI US, rate en `whoami`)  
> **Producto:** [`../PLATFORM_API.md`](../PLATFORM_API.md) §4.2 · §11  
> **Fase:** A (junto a M1)  
> **Par:** [`pa_auth.md`](pa_auth.md)  
> **HMAC de webhooks:** detalle en [`pa_webhooks.md`](pa_webhooks.md) (M8); aquí la lista blanca anti-SSRF

---

## Propósito

Congelar reglas que la capa HTTP **no puede saltarse**, aunque el runner de la app sea correcto. Complementa auth (quién entra) con **cómo se procesa** (qué se loguea, qué se descarga, qué se rechaza).

Los jobs (`POST /jobs/run`) aún no existen: el servicio y la política quedan listos para M3–M5.

---

## Qué hay en código

| Pieza | Dónde |
|-------|--------|
| Política por compañía | `ApiProcessPolicy` (OneToOne `Company`) |
| Helpers | `apps.platform_api.services.process_security_service` |
| Rate limit | `GET /api/v1/whoami` tras Bearer válido (429) |
| UI US | `/app/platform-api/seguridad/` |

Campos ajustables por US: tamaño (MB), rate/minuto por key, TTL artifacts, extensiones, hosts de callback. Fijos: `require_published=True`, `dry_run_counts_in_dashboard=False`.

Default de upload: **50 MB** y tipos tipo intake (`.txt` `.csv` `.tsv` `.xlsx` `.xls` `.xml` `.json`).

---

## Reglas

| Tema | Regla |
|------|--------|
| Solo publicado | Productivo = versión publicada — `ensure_published` |
| Artifacts | Token firmado (`TimestampSigner`) + TTL de la política — `sign_artifact_token` / `verify_artifact_token` |
| PII | `redact_for_log`: no cuerpos, tokens ni celdas |
| Idempotencia | `idempotency_fingerprint` (key + hash) — se usará en [`pa_jobs_ops.md`](pa_jobs_ops.md) |
| Cuotas | Rate y tamaño por compañía / key |
| Replay / IDs | `opaque_not_found` → 404 |
| Upload | `validate_upload` (extensión + bytes) |
| Dry-run | `dry_run_in_dashboard` siempre falso |
| Callback | `validate_callback_url`: HTTPS, sin userinfo, sin host privado/localhost, host en allowlist |

---

## UI y URLs

| Ruta | Pantalla |
|------|----------|
| `/app/platform-api/seguridad/` | Editar política |
| `/app/platform-api/seguridad/ayuda/` | Ayuda |

Sidebar US: **Seguridad API**. Listado de clientes: botón **Seguridad**.

---

## Relacionados

[`pa_auth.md`](pa_auth.md) · [`pa_jobs_ops.md`](pa_jobs_ops.md) · [`pa_webhooks.md`](pa_webhooks.md) · [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) §3.17 · [`../PLATFORM_API.md`](../PLATFORM_API.md) §4.2
