# Integración transversal — File Watch

Cómo encaja la **bandeja** con **Scheduler**, **Pipeline**, **PLATFORM API**, historiales de app y el **worker Railway**. No define pantallas CRUD nuevas (eso es M1–M9).

> **Estado:** **Diseño M10** (spec + prototipo mapa HTML); app Django / bridge tick pendiente de OK  
> **Producto:** [`../FILE_WATCH.md`](../FILE_WATCH.md) §4 · §5 · §8  
> **Índice:** [`README.md`](README.md)  
> **Previo:** avisos [`wach_notify.md`](wach_notify.md)  
> **Prototipos:** mapa [`../../prototype/file_watch/watch_integration.html`](../../prototype/file_watch/watch_integration.html) · ayuda [`watch_integration_help.html`](../../prototype/file_watch/watch_integration_help.html)  
> **Rama:** `diseno_desarrollo_FILE_WATCH`

---

## Modelo único: disparador → Job

```text
UI Ejecutar ────────────┐
PLATFORM API ───────────┤
File Watch (llegó / fire) ─┼→ mismo runner (kind + versión publicada
File Scheduler (hora / dep.) ─┤     o pipeline_id) → historial app / tablero
```

Watch **no** es otro ETL ni otro Scheduler. Detecta, materializa lote (hash) y, según M5, dispara o deja `pending`.

| Capa | Pregunta | Doc |
|------|----------|-----|
| **De dónde** | ¿SFTP / carpeta / API push? | M2 [`wach_source.md`](wach_source.md) |
| **Qué archivo** | ¿Lote + hash en storage? | M3 [`wach_intake.md`](wach_intake.md) |
| **Hacia qué runner** | Job / pipeline / diferir | M4 [`wach_route.md`](wach_route.md) |
| **¿Cuándo encolar?** | Al llegar vs solo pending | M5 [`wach_fire.md`](wach_fire.md) |
| **Cuándo (reloj)** | Cron del plan | [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) |

**File Gate no configura IFS.** Las rutas viven en Watch.

---

## File Scheduler (producto §4)

| Watch | Scheduler |
|-------|-----------|
| ¿Llegó el archivo? | ¿Es la hora / terminó A? |
| Origen SFTP, carpeta, `api_push` | Cron o dependencia |
| `fire_mode=on_arrival` → Job ya | `input_origin=watch` + **código de bandeja** (no hash) |
| `fire_mode=pending_only` → lote `pending` | Tick hace **claim** del lote → `content_hash` → mismo runner |

### Puente obligatorio (hoy roto)

1. Plan Destino: `input_origin=watch`, campo **Código de la bandeja** = `slug` Watch.  
2. Worker tick: resolver lote `pending` (FIFO/LIFO M3) → claim → invocar runner con ese hash.  
3. Sin pending → **`schedule_missing_input`** (código Scheduler, no `watch_*`).  
4. Hash ausente en storage → `schedule_artifact_not_found`.

Estado actual del producto: el plan ya guarda `watch_id`; el tick **aún no** resuelve el lote ([`sch_tick.md`](../definition_app_FILE_SCHEDULER/sch_tick.md)). Este módulo define el contrato; la implementación del bridge es parte de «Desarrolla el módulo» Watch + ajuste Scheduler.

No se duplican listeners SFTP en el plan.

---

## File Pipeline

| Rol | Qué hace Watch | Qué no hace |
|-----|----------------|-------------|
| Destino fire | `route_mode=pipeline` + `pipeline_id` (M4) si `on_arrival` | Diseñar pasos |
| Destino diferido | Plan Scheduler con `target_mode=pipeline` + claim del lote | — |
| Fire | `start_run`; `trigger_source=file_watch`; `watch_id` / `batch_id` | Informe por paso (abrir el run) |
| Tablero | Runs con `trigger_source=file_watch` alimentan el tablero | Sustituir dashboard Pipeline |

Paso “Watch” **dentro** del canvas de Pipeline: fuera de MVP (forma de trabajo: origen = adaptador de bandeja, no nodo de diseñador).

---

## PLATFORM API

| Tema | MVP |
|------|-----|
| CRUD de bandejas | **Fuera** de API (consola US PA/ED). Admin API futura. |
| Adaptador `api_push` | Endpoint de llegada a la bandeja (hermano; no sustituye POST que dispara Job) |
| Run disparado por Watch | Job/`pipeline_run` con `trigger_source=file_watch` + `watch_id` + `batch_id` |
| Webhooks de aviso | Misma firma que [`pa_webhooks.md`](../definition_app_PLATFORM_API/pa_webhooks.md) (M9) |
| Auditoría de máquina | [`pa_audit.md`](../definition_app_PLATFORM_API/pa_audit.md) — no el CRUD de la bandeja |

---

## Tablero e historiales

- Pipeline: filtro `trigger_source=file_watch`.  
- Watch UI: **Lotes** (M3) y **Auditoría** (M7).  
- Jobs sueltos (Gate, Clean…): historial de **esa app**.  
- Scheduler Actividad: ticks del plan (incluye missing_input si no hay lote).

---

## Railway / worker

| Pieza | Rol |
|-------|-----|
| Web Django | CRUD bandeja M1–M9 (cuando exista `apps.file_watch`) |
| Worker Watch | Poll SFTP / carpeta; intake; apply M6; fire M5 o dejar pending |
| Worker Scheduler | Claim pending por `watch_id` (bridge) |
| Cola | Mismo encolado `run_*_job` / pipeline que UI/API |
| Identidad | `system:file_watch` · `system:scheduler` — no bypasean `company_id` |

Deploy productivo: rama `main`. Diseño no fija librería de poll concreta.

---

## Autorización (recorte integración)

Crear bandeja = US PA/ED. Config = PA/ED de la bandeja. Monitor/fire = sistema. Destinos: el sistema debe poder ejecutar el proyecto/pipeline o se deniega el fire. Ver [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md).

---

## Checklist de bridge (aceptación integración)

- [ ] Claim atómico `pending` → `consumed` con `consumed_by=schedule:…` o `fire:…`  
- [ ] Tick con `watch_id` deja de fallar siempre con `schedule_missing_input` cuando hay lote  
- [ ] `trigger_source` + ids en el Job  
- [ ] Artifact (hash fijo en plan) ≠ Watch (código de bandeja) documentado en UI Destino  
- [ ] Sin IFS en Gate/Pipe  

---

## Fuera de alcance de este archivo

- Pantallas M1–M9.  
- Implementar workers.  
- Nodo Watch en canvas Pipeline.

---

## Criterio de aceptación del módulo (diseño)

- [x] Mapa Scheduler / Pipeline / API / Railway.  
- [x] Contrato claim + códigos frontera.  
- [x] Prototipo de referencia (no formulario de bandeja).

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`../FILE_WATCH.md`](../FILE_WATCH.md) | Producto |
| [`../definition_app_FILE_SCHEDULER/sch_integration.md`](../definition_app_FILE_SCHEDULER/sch_integration.md) | Hermano |
| [`../definition_app_FILE_SCHEDULER/sch_target.md`](../definition_app_FILE_SCHEDULER/sch_target.md) · [`sch_tick.md`](../definition_app_FILE_SCHEDULER/sch_tick.md) | `watch_id` / claim |
| [`wach_intake.md`](wach_intake.md) · [`wach_fire.md`](wach_fire.md) | Lote / modos |
| [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) | Destino pipeline |
| [`../PLATFORM_API.md`](../PLATFORM_API.md) | Disparador hermano |
