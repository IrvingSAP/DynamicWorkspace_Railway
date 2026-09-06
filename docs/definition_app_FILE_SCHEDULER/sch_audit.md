# Módulo 7 — Auditoría (CRUD + tick)

Registro **append-only** del plan: quién cambió la definición y qué hizo cada disparo. No copia el historial de filas de Gate ni los pasos de Pipeline: **enlaza** `job_id` / `pipeline_run_id`.

> **Estado:** **Implementado (M7)** (`apps.file_scheduler` · `services/schedule_audit.py` · `templates/file_scheduler/audit/`)  
> **Producto:** [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) §7  
> **Índice:** [`README.md`](README.md)  
> **Previo:** dependencia [`sch_dependency.md`](sch_dependency.md)  
> **Siguiente:** errores [`sch_errors.md`](sch_errors.md)  
> **Prototipos:** [`../../prototype/file_scheduler/schedule_audit.html`](../../prototype/file_scheduler/schedule_audit.html) · vacío [`schedule_audit_empty.html`](../../prototype/file_scheduler/schedule_audit_empty.html) · ayuda [`schedule_audit_help.html`](../../prototype/file_scheduler/schedule_audit_help.html)  
> **Rama:** `diseno_desarrollo_FILE_SCHEDULER`

---

## Propósito

```text
Plano A — Definición (CRUD)
  created / updated / paused / resumed / archived
Plano B — Disparo (tick)
  tick_enqueued / tick_skipped / tick_failed  [+ notify_sent en M9]
       → job_id o pipeline_run_id  (detalle en la app o Pipeline §7.1)
```

**No hay ejecución anónima.** Actor humano (**US** en alta; US o UF miembro del plan en el resto) o `system:scheduler`. Sin PII de celdas: metadatos, hashes, ids, `error_code`. No bytes de archivo.

PLATFORM API MVP **no** audita el diseño de schedules (CRUD fuera de API). El fire sí deja `trigger_source` + `schedule_id` en el run delegado.

---

## Relación con Actividad (M4)

| Pantalla | Qué muestra |
|----------|-------------|
| **Actividad** | Ticks operativos (ventanas, encoló / omitió / falló, run) |
| **Auditoría** | Timeline completo: CRUD **y** ticks, con actor, diff resumido, `correlation_id` |

M4 no sustituye M7. Un tick en Actividad tiene **la misma** fila de evento `schedule.tick_*` aquí.

---

## Acción en el hub

Enlace **Auditoría** (operación) → listado append-only de **este** plan. Todos los roles de lectura. Nadie edita ni borra un evento en MVP.

Borrado de evidencia = soft + política PA (paridad UI/API); **fuera de MVP** como botón. No hay hard-delete de filas de auditoría.

---

## Eventos (catálogo)

| Evento | Plano | Actor típico | Payload mínimo |
|--------|-------|--------------|----------------|
| `schedule.created` | A | US (`created_by`) | `company_id`, slug, name, visibility, status |
| `schedule.updated` | A | US o UF miembro PA/ED | Diff: cron, timezone, destino, solape, `trigger_mode` / padre |
| `schedule.paused` | A | US o UF miembro PA/ED | `active` → `inactive` |
| `schedule.resumed` | A | US o UF miembro PA/ED | `inactive` → `active` |
| `schedule.archived` | A | PA | timestamp |
| `schedule.tick_enqueued` | B | `system:scheduler` | `scheduled_for` o `parent_*_id`, `trigger_source`, `job_id` **o** `pipeline_run_id`, `correlation_id` |
| `schedule.tick_skipped` | B | sistema | motivo (`schedule_overlap_skip`, misfire, …) |
| `schedule.tick_failed` | B | sistema | `error_code` del Scheduler (antes de encolar) |
| `schedule.notify_sent` | B | sistema | M9; destinatario tipo, no cuerpo de archivo |

Cada evento: `id`, `schedule_id`, `company_id`, `occurred_at`, `actor_id` o `system:scheduler`, `event`, `payload` JSON (sin celdas).

---

## Plano B — campos de disparo

Alinear producto §7-B. El run delegado **repite** `trigger_source` (`scheduler` \| `dependency`), `schedule_id`, ventana o padre.

| Campo | Uso |
|-------|-----|
| `schedule_id` | Plan |
| `trigger_source` | `scheduler` · `dependency` |
| `scheduled_for` | Ventana (modo time) |
| `parent_job_id` / `parent_pipeline_run_id` | Modo dependency |
| `triggered_by` | `system:scheduler` |
| `correlation_id` | Traza Scheduler → Job / pipeline |
| `job_id` / `pipeline_run_id` | Enlace; **mismo** id que la UI de la app y `GET` API |
| `retry_of_run_id` | Si es reintento (nuevo run) |

El **resultado de negocio** (Gate rechazó) **no** se duplica: abrir el enlace.

---

## Autorización

| Acción | PA | ED | GE | CO |
|--------|----|----|----|-----|
| Ver auditoría del plan | ✓ | ✓ | ✓ | ✓* |
| Exportar / borrar evidencia | PA (futuro) | — | — | — |

\*CO/GE: metadatos de eventos; sin nombres de archivo sensibles si el producto los oculta; nunca contenido de celdas.

Otra compañía → 404 opaco.

---

## UI (listado)

Paridad planes / actividad: DataTables (Buscar, 10/25/50/100). Filtro de toolbar: **Todos** · **Definición** · **Tick**. Orden por `occurred_at` descendente.

Columnas: cuándo, evento, actor, resumen, enlace (run o —).

Estado vacío: plan recién creado → al menos `schedule.created` (nunca timeline en blanco tras el alta).

---

## Fuera de alcance

- Informe por paso de pipeline.  
- Auditoría HTTP de clientes API (`pa_audit.md`).  
- Códigos `user_message` de catálogo (M8).  
- Cuerpo de `schedule.notify_sent` (M9).

---

## Criterio de aceptación (diseño)

- [x] Dos planos; append-only; sin PII de celdas.  
- [x] Tick encola con enlace `job_id` / `pipeline_run_id`.  
- [x] CRUD y ticks en una timeline filtrable.  
- [x] Prototipos HTML.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) | §7 |
| [`sch_lifecycle.md`](sch_lifecycle.md) | Eventos A |
| [`sch_tick.md`](sch_tick.md) | Eventos B · Actividad |
| [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) | §7.1 — no duplicar pasos |
| [`../definition_app_PLATFORM_API/pa_audit.md`](../definition_app_PLATFORM_API/pa_audit.md) | Plano máquina; no CRUD de schedule |
| [`README.md`](README.md) | Índice |
