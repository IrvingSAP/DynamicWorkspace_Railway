# Integración transversal — File Scheduler

Cómo encaja el plan con **Watch**, **Pipeline**, **PLATFORM API**, **tablero** y el **worker Railway**. No define pantallas de CRUD nuevas de un plan (eso es M1–M9).

> **Estado:** **Implementado (M10)** (`apps.file_scheduler.services.schedule_integration` · `…/integracion/` · filtro `trigger` en tablero Pipeline)  
> **Producto:** [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) §3 · §4 · §9 · §10 tablero  
> **Índice:** [`README.md`](README.md)  
> **Previo:** avisos [`sch_notify.md`](sch_notify.md)  
> **Prototipos:** mapa [`../../prototype/file_scheduler/schedule_integration.html`](../../prototype/file_scheduler/schedule_integration.html)  
> **Rama:** `diseno_desarrollo_FILE_SCHEDULER`

---

## Modelo único: disparador → Job

```text
UI Ejecutar ────────────┐
PLATFORM API ───────────┤
File Watch (llegó) ─────┼→ mismo runner (kind + versión publicada
File Scheduler (hora / dependencia) ──┤     o pipeline_id) → **mismo runner** → historial app / tablero
Dependencia (tras A) ───┘
```

Un solo semántica de Job. El Scheduler **no** es otro ETL ni otro Watch.

| Capa | Pregunta | Doc |
|------|----------|-----|
| **Cuándo** | ¿Es la hora o terminó A? | Este producto · M2 · M6 |
| **Dónde está el fichero** | Watch / artifact / none | [`../FILE_WATCH.md`](../FILE_WATCH.md) · M3 |
| **Cómo se transforma** | App o pipeline | Gate, Pipe, Clean, … · [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) |

**File Gate no configura IFS.** El tick con `artifact_ref` resuelve el hash en storage e invoca el runner de la app ([`sch_tick.md`](sch_tick.md)).

---

## Watch (producto §4)

| Watch | Scheduler |
|-------|-----------|
| ¿Llegó el archivo? | ¿Es la hora / terminó A? |
| Origen SFTP, carpeta, drop | Cron o dependencia |
| Puede disparar un Job **al llegar** | Puede disparar **a las 02:00** usando el lote que Watch ya tiene (`input_origin=watch`) |

No se duplican listeners. El plan **elige** un `watch_id` (M3); la config de ruta vive en Watch.

Combinado típico: Watch ingesta el extracto; Scheduler reintenta fallidos o lanza Match de cierre.

---

## File Pipeline

| Rol | Qué hace el Scheduler | Qué no hace |
|-----|------------------------|-------------|
| Destino | `target_mode=pipeline` + `pipeline_id` activo y publicado (M3) | Diseñar pasos, publicar versiones |
| Fire | Encola `pipeline_run`; `trigger_source=scheduler` o `dependency`; `schedule_id` | Informe OK/ERROR por paso (abrir el run) |
| Tablero | Runs con esos `trigger_source` **alimentan** el tablero de Pipeline | Sustituir [`../definition_app_FILE_PIPELINE/pipeline_dashboard.md`](../definition_app_FILE_PIPELINE/pipeline_dashboard.md) |

Jobs sueltos (Gate, Pipe, …): historial de **esa app**, no el tablero de pipelines (salvo producto unificado futuro).

Nodo “schedule” **dentro** del diseñador de pipeline: forma de trabajo §3 **abierta**. Este MVP asume **plan de plataforma** + worker, no un paso más del canvas.

---

## PLATFORM API

| Tema | MVP |
|------|-----|
| CRUD de schedules | **Fuera** de API (producto §7-A). Consola **US** (alta: US PA/ED). |
| Run disparado por el worker | El Job/`pipeline_run` lleva `trigger_source` + `schedule_id`; `GET` jobs igual que UI |
| Crear schedules por HTTP | Admin API **futura**; no bloquea M1–M9 |
| Webhooks de aviso | Reutilizar firma [`../definition_app_PLATFORM_API/pa_webhooks.md`](../definition_app_PLATFORM_API/pa_webhooks.md) (M9) |
| Auditoría de máquina | [`pa_audit.md`](../definition_app_PLATFORM_API/pa_audit.md) — no el CRUD del plan |

Idempotencia de ventana del Scheduler ≠ `Idempotency-Key` HTTP, mismo *espíritu* (un slot = un fire).

---

## Tablero

- Pipeline: filtro / columna `trigger_source=scheduler` (y `dependency`).  
- Scheduler UI: **Actividad** y **Auditoría** del plan (M4, M7).  
- Dry-run / “próxima ejecución” del preview M2: **no** entra al pulso del tablero.

---

## Railway / worker

| Pieza | Rol |
|-------|-----|
| Web Django | CRUD del plan (M1–M3, M5, M6, M9), lectura Actividad/Auditoría |
| Worker (proceso) | Evalúa planes `active` modo `time` (M4); hook de fin de Job para `dependency` (M6) |
| Cola | Encolar `run_*_job` / pipeline; `schedule_enqueue_failed` si no acepta |
| Reloj | UTC interno; `scheduled_for` en IANA del plan |

Deploy productivo: rama `main` (README). Este diseño no elige librería de cron concreta.

Misfire y solape: M4 · M5. El worker **no** bypasea tenancy (producto §9): `company_id` del plan; permisos de **cada** proyecto destino.

---

## Autorización (recorte integración)

PA/ED configuran el plan. Tick = `system:scheduler`. Destinos: el sistema debe poder ejecutar todos los proyectos del pipeline o se deniega el fire completo. Ver [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md).

Membresía propia vs heredar del proyecto: abierta en M1; no bloquea este mapa.

---

## Forma de trabajo (producto §3)

Sigue **abierta**. Este paquete de specs asume:

1. UI de planes + **worker/monitor** (prioridad de implementación).  
2. Adaptador API de CRUD de schedules = posterior.  
3. Nodo schedule en el canvas de Pipeline = posterior (mismas reglas §7–§10).

---

## Fuera de alcance de este archivo

- Reescribir M2–M9.  
- Specs de Watch o del diseñador de Pipeline.

---

## Criterio de aceptación (diseño)

- [x] Fronteras Watch / Pipeline / API / tablero / worker escritas.  
- [x] `trigger_source` y `schedule_id` en el run delegado.  
- [x] §3 marcado abierto; MVP = UI + worker.  
- [x] Prototipo mapa (referencia, no CRUD).  
- [x] Pantalla de mapa en la app y filtro de tablero por disparo.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) | §3 · §4 · §9 · §10 |
| [`../FILE_WATCH.md`](../FILE_WATCH.md) | Llegada |
| [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) | Destino cadena · tablero |
| [`../PLATFORM_API.md`](../PLATFORM_API.md) | Hermano HTTP |
| [`../APP_FACTORY_FILE_OPS.md`](../APP_FACTORY_FILE_OPS.md) | `artifact_ref` |
| [`README.md`](README.md) | Índice M1–M9 |
