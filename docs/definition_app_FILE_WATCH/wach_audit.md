# Módulo 7 — Auditoría (CRUD + llegada)

Registro **append-only** de la bandeja: quién cambió la definición y qué pasó con cada llegada / claim / fire. No copia el historial de filas de Gate ni los pasos de Pipeline: **enlaza** `job_id` / `pipeline_run_id` / `batch_id`.

> **Estado:** **Diseño M7** (spec + prototipos HTML); implementación Django pendiente de OK  
> **Producto:** [`../FILE_WATCH.md`](../FILE_WATCH.md) · contrato Pipeline §6 · §7 · PLATFORM API §9  
> **Índice:** [`README.md`](README.md)  
> **Previo:** idempotencia [`wach_idempotency.md`](wach_idempotency.md)  
> **Siguiente:** errores [`wach_errors.md`](wach_errors.md) · notify [`wach_notify.md`](wach_notify.md)  
> **Prototipos:** [`../../prototype/file_watch/watch_audit.html`](../../prototype/file_watch/watch_audit.html) · vacío [`watch_audit_empty.html`](../../prototype/file_watch/watch_audit_empty.html) · ayuda [`watch_audit_help.html`](../../prototype/file_watch/watch_audit_help.html)  
> **Rama:** `diseno_desarrollo_FILE_WATCH`

---

## Propósito

```text
Plano A — Definición (CRUD / config)
  created / updated / paused / resumed / archived
  source_* / route_* / fire_* / intake_policy_* / idempotency_*
  members (si se audita aquí o en chasis)

Plano B — Llegada / lote / fire
  batch_ingested / batch_skipped / batch_claim / batch_intake_failed
  fired / fire_failed / fire_skipped / notify_sent (M9)
       → batch_id + content_hash (metadatos)
       → job_id o pipeline_run_id cuando aplica
```

**No hay llegada anónima.** Actor humano (US en alta; miembro PA/ED en config) o `system:file_watch` / `system:scheduler` (claim). Sin PII de celdas: metadatos, hashes, ids, `error_code`. No bytes de archivo ni secretos (password/token).

PLATFORM API MVP **no** audita el CRUD de bandejas. El fire/claim deja traza en el run delegado (`trigger_source` + `watch_id` / `batch_id` — M10).

---

## Relación con Llegadas / lotes (M3)

| Pantalla | Qué muestra |
|----------|-------------|
| **Llegadas / lotes** (M3) | Estado operativo de cada lote (pending, consumed, …) |
| **Auditoría** (este módulo) | Timeline completo: CRUD **y** eventos de lote/fire, con actor y payload |

Un `watch.batch_ingested` en Auditoría corresponde al alta del lote visible en Intake. M3 no sustituye M7.

---

## Acción en el hub

Enlace **Auditoría** (operación) → listado append-only de **esta** bandeja. Todos los roles de lectura (CO/GE: sin secretos; ya no hay secretos en payload). Nadie edita ni borra un evento en MVP.

Borrado de evidencia = soft + política PA; **fuera de MVP**. No hay hard-delete.

---

## Eventos (catálogo)

### Plano A — definición

| Evento | Actor típico | Payload mínimo |
|--------|--------------|----------------|
| `watch.created` | US (`created_by`) | `company_id`, slug, name, visibility, status |
| `watch.updated` | PA/ED | Diff: name, description, visibility |
| `watch.paused` | PA/ED | `active` → `inactive` |
| `watch.resumed` | PA/ED | `inactive` → `active` |
| `watch.archived` | PA | timestamp |
| `watch.source_updated` | PA/ED | kind, paths/patterns, poll, after_detect, `secret_ref` id (**no** valor) |
| `watch.source_tested` | PA/ED | ok/fail, latency opcional |
| `watch.push_token_rotated` | PA | timestamp (sin token) |
| `watch.route_updated` | PA/ED | `route_mode`, kind/project o pipeline_id |
| `watch.fire_updated` | PA/ED | `fire_mode` |
| `watch.intake_policy_updated` | PA/ED | settle, max_bytes, pick_policy |
| `watch.idempotency_updated` | PA/ED | snapshot políticas |

### Plano B — llegada / fire

| Evento | Actor típico | Payload mínimo |
|--------|--------------|----------------|
| `watch.batch_ingested` | `system:file_watch` | `batch_id`, `content_hash`, size, filename, `source_kind` |
| `watch.batch_skipped` | sistema | razón `duplicate` / `quota_*`, hash |
| `watch.batch_intake_failed` | sistema | `error_code`, filename si hay |
| `watch.batch_claim` | `system:file_watch` · `system:scheduler` · API | `batch_id`, `consumed_by` |
| `watch.fired` | `system:file_watch` | `batch_id`, hash, `job_id` **o** `pipeline_run_id`, `correlation_id` |
| `watch.fire_failed` | sistema | `error_code`, `batch_id` |
| `watch.fire_skipped` | sistema | motivo (p. ej. bandeja inactive en carrera) |
| `watch.retry_scheduled` | sistema | intento n, backoff |
| `watch.notify_sent` | sistema | M9; tipo destinatario, no cuerpo de archivo |

Cada evento: `id`, `watch_id` (slug o FK), `company_id`, `occurred_at`, `actor_id` o actor sistema, `event`, `payload` JSON.

---

## Enlace a Job / run

| Campo en payload | Uso |
|------------------|-----|
| `batch_id` | Lote M3 |
| `content_hash` | Metadato; no sustituye Artifact del plan |
| `job_id` / `pipeline_run_id` | Mismo id que historial de app / Pipeline |
| `correlation_id` | Traza Watch → runner |
| `consumed_by` | `fire:…` · `schedule:{slug}` · `manual` · API |
| `trigger_source` (en el Job) | p. ej. `file_watch` · `scheduler` (M10) |

Auditoría **no** duplica filas Gate/Pipe: solo el enlace.

---

## Autorización

| Acción | PA | ED | GE | CO |
|--------|----|----|----|-----|
| Ver timeline | ✓ | ✓ | ✓ | ✓ |
| Editar / borrar eventos | — | — | — | — |

Filtro por plano (A / B) y por tipo de evento en UI.

---

## UI

Columnas: fecha, evento, plano, actor, resumen (hash corto / job / diff), enlace si hay run.

Filtros: plano, tipo de evento + DataTables buscar (paridad Scheduler).

Estado vacío: mensaje + enlace al hub.

---

## Fuera de alcance

- Auditoría HTTP de máquina (PLATFORM API).  
- Diff de bytes o preview de archivo.  
- Soft-delete de evidencia en MVP.

---

## Criterio de aceptación del módulo (diseño)

- [x] Catálogo plano A + B alineado a M1–M6 / M9.  
- [x] Append-only; sin secretos ni PII de celdas.  
- [x] Enlace `job_id` / `pipeline_run_id` / `batch_id`.  
- [x] Prototipos listado + vacío + ayuda.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`wach_lifecycle.md`](wach_lifecycle.md) | Eventos CRUD |
| [`wach_intake.md`](wach_intake.md) | Lotes |
| [`wach_fire.md`](wach_fire.md) | `watch.fired` |
| [`../definition_app_FILE_SCHEDULER/sch_audit.md`](../definition_app_FILE_SCHEDULER/sch_audit.md) | Patrón hermano |
| [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) | §7 · §7.1 historial run |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Textos al implementar |
