# Módulo 4 — Tick (worker / encolar / misfire)

El **worker** evalúa planes `active` y, en cada ventana `scheduled_for`, intenta **encolar** el Job o pipeline del destino. La UI de este módulo es el **historial de ticks del plan**, no el historial de Gate/Pipe ni el tablero de pasos.

> **Estado:** **Implementado (M4)** (`apps.file_scheduler`: `ScheduleTick`, worker `process_schedule_ticks`, UI Actividad)  
> **Producto:** [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) §3 worker · §7-B · §8 · §10 (idempotencia / entrada)  
> **Índice:** [`README.md`](README.md)  
> **Previo:** destino [`sch_target.md`](sch_target.md)  
> **Siguiente:** solape [`sch_overlap.md`](sch_overlap.md)  
> **Prototipos:** [`../../prototype/file_scheduler/schedule_activity.html`](../../prototype/file_scheduler/schedule_activity.html) · vacío [`schedule_activity_empty.html`](../../prototype/file_scheduler/schedule_activity_empty.html) · ayuda [`schedule_activity_help.html`](../../prototype/file_scheduler/schedule_activity_help.html)  
> **Rama:** `diseno_desarrollo_FILE_SCHEDULER`

---

## Propósito

```text
Plan active + M2 + M3 válidos
  → Worker (este módulo): ¿es esta ventana?
  → Resolver entrada (Watch / artifact / none)
  → Encolar Job o pipeline_run
  → Auditar tick (plano B)
```

Este módulo define **contrato del fire** y la **pantalla Actividad**. No configura cron ni destino. No parsea archivos. No sustituye Pipeline §7.1 (pasos): se **enlaza** `job_id` / `pipeline_run_id`.

**Actor del fire:** `system:scheduler` en nombre de la `company_id` del plan. **No** bypasea tenancy ni permisos de los proyectos destino (producto §9).

---

## Acción en el hub

Enlace **Actividad / ticks** → listado de ticks de **este** plan (todos los roles de lectura). PA/ED no “editan” un tick: el historial es append-only.

**No hay «Ejecutar ahora»** en este MVP (paridad M1). Un disparo manual sería otro fire con `scheduled_for` distinto o un producto futuro; no reescribe un tick fallido.

---

## Condiciones para considerar el plan

El worker **solo** evalúa un plan si:

1. `status = active` (no `in_progress`, `inactive`, `archived`).
2. Programación M2 válida.
3. Destino M3 válido (versión publicada al **instante de encolar**).

Si no está `active` → no encola; si alguien fuerza un fire → `schedule_paused`. No hay tick anónimo.

---

## Ventana e idempotencia

| Concepto | Regla |
|----------|--------|
| `scheduled_for` | Instante de la ventana en la **timezone del plan** (M2). Misma función que el preview de 3 slots. |
| Clave | `schedule_id` + `scheduled_for` = **un** fire. No dos encolados para el mismo slot. |
| Reloj del worker | Puede ir en UTC; la ventana se interpreta en IANA del plan. |

Reintento humano o de política = **nuevo** run (`retry_of_run_id`), no reescribir el tick fallido (API §10.1; Pipeline §7.1-D). Detalle de solape si el run anterior **sigue vivo**: [`sch_overlap.md`](sch_overlap.md) — default de producto: **skip** (`schedule_overlap_skip`).

---

## Flujo del worker (un slot)

```text
1. Plan active + M2 + M3
2. Slot due (scheduled_for ≤ now, aún no fireado)
3. ¿Solape? → M5 (MVP: skip + tick_skipped)
4. ¿Versión publicada vigente? Si no → no encolar, tick_failed, schedule_no_published_target
5. ¿Entrada? Watch / artifact / none según M3
     Si falta → no encolar, tick_failed, schedule_missing_input (no inventar archivo)
6. Resolver artifact en storage (hash) e invocar el **mismo runner** de la app (`run_clean_job`, `validate_and_run`, `run_full_job`) o `pipeline start_run`
7. tick_enqueued + enlace `job_id` o `pipeline_run_id` (el id del Job de la app, p. ej. `CleanJob`)
     Si no hay archivo en storage → `schedule_artifact_not_found`
     Si el kind no tiene runner cableado → `schedule_runner_unsupported`
     Si el runner no puede arrancar → `schedule_enqueue_failed`
```

El **resultado de negocio** del Job (Gate rechazó, Pipe con errores) **no** es un código `schedule_*`: el tick queda **Encolado** si el runner arrancó; el OK/ERROR se lee en la app o en el `pipeline_run_id`. El Scheduler registra que **disparó el runner** (o que no pudo **antes** de ejecutarlo).

---

## Misfire

`schedule_misfire`: el worker estaba caído o tarde y la ventana `scheduled_for` ya pasó **sin** fire.

**Política MVP:** **no** ponerse al día disparando N ventanas atrasadas de golpe (evita avalancha). Registrar `tick_skipped` / `tick_failed` con `schedule_misfire` para cada ventana perdida (o un resumen operativo) y continuar con la **siguiente** ventana futura. Catch-up masivo = fuera de MVP (M5/ops).

---

## Estados de un tick (UI)

Independientes del `status` del **plan**.

| Valor | UI | Significado |
|-------|-----|-------------|
| `enqueued` | Encolado | Se creó el Job/run delegado |
| `skipped` | Omitido | No encoló (solape, pausado al evaluar, misfire de política skip) |
| `failed` | Falló | Error **del Scheduler** al validar o encolar (`schedule_*`) |
| `running` | En curso | El run delegado sigue vivo (lectura; detalle en la app/pipeline) |

La pantalla muestra `scheduled_for`, resultado del tick, `error_code` si aplica, y enlace al run. No muestra celdas del archivo.

Listado (paridad planes): DataTables — **Buscar**, **Mostrar** 10/25/50/100, paginación. Filtro de toolbar por estado de tick (Todos / Encolado / Omitido / Falló / En curso). Orden por ventana descendente.

---

## Autorización

| Acción | PA | ED | GE | CO |
|--------|----|----|----|-----|
| Ver actividad del plan | ✓ | ✓ | ✓ | ✓ |
| Disparar tick (sistema) | — | — | — | — |
| Cancelar el **run delegado** | Según la app/pipeline | Según la app/pipeline | — | — |

Cancelar aborta el job/run, **no** borra el plan ni el evento de tick (producto §10). Configurar el plan sigue siendo M1–M3.

Compañía inactiva o plan de otra company → no listar ticks (404 opaco).

---

## Relación con otros módulos

| Módulo | Rol |
|--------|-----|
| M1 | Solo `active` dispara |
| M2 | Calcula `scheduled_for` |
| M3 | Destino + entrada; revalidar al fire |
| M5 | Solape skip/queue |
| M6 | `trigger_source=dependency` (otro disparador; no este worker de cron) |
| M7 | Campos append-only del tick (detalle de auditoría) |
| M8 | Catálogo `schedule_*` + `user_message` |
| M9 | Correo/webhook **después** del tick fallido o del run |

---

## Auditoría (plano B, mínimo)

Eventos: `schedule.tick_enqueued` · `schedule.tick_skipped` · `schedule.tick_failed`.  
Campos: `triggered_by=system:scheduler`, `scheduled_for`, `company_id`, `correlation_id`, `job_id` / `pipeline_run_id` si hay, `error_code` si falló. Sin PII de celdas. Snapshot de cron/ventana y destino ids.

Detalle de esquema: M7. Este módulo fija **qué** se emite al fire.

---

## Fuera de alcance

- Código Django, cola Railway, proceso daemon.  
- Informe OK/ERROR por paso de pipeline (abrir el run).  
- Política fina de solape (M5) y dependencias “tras A” (M6).  
- «Ejecutar ahora».

---

## Criterio de aceptación (diseño)

- [x] Worker solo planes `active` con M2+M3; identidad `system:scheduler`.  
- [x] Un fire por `schedule_id` + `scheduled_for`.  
- [x] Misfire: no avalancha; código `schedule_misfire`.  
- [x] Entrada ausente → `schedule_missing_input`; sin archivo inventado.  
- [x] UI Actividad: ticks del plan + enlace al run; vacío si aún no hay fires.  
- [x] Sin «Ejecutar ahora».  
- [x] Prototipos HTML.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) | §3 · §7-B · §8 · §10 |
| [`sch_lifecycle.md`](sch_lifecycle.md) | Estado `active` |
| [`sch_cron.md`](sch_cron.md) | `scheduled_for` |
| [`sch_target.md`](sch_target.md) | Encolar destino |
| [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) | `trigger_source=scheduler`; no duplicar pasos |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Textos al implementar |
| [`README.md`](README.md) | Índice |
