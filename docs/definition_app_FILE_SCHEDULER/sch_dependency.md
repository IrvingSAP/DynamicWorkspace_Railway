# Módulo 6 — Dependencia (“tras Job A”)

Un plan puede dispararse **cuando termina otro Job o pipeline**, no (solo) por el reloj. El run delegado lleva `trigger_source=dependency` (Pipeline §7.1-B).

> **Estado:** **Implementado (M6)** (`apps.file_scheduler`: `trigger_mode`, padre, hook al terminar, `trigger_source=dependency`)  
> **Producto:** [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) §2 · §7-B  
> **Índice:** [`README.md`](README.md)  
> **Previo:** solape [`sch_overlap.md`](sch_overlap.md)  
> **Siguiente:** auditoría [`sch_audit.md`](sch_audit.md)  
> **Prototipos:** [`../../prototype/file_scheduler/schedule_dependency.html`](../../prototype/file_scheduler/schedule_dependency.html) · ayuda [`schedule_dependency_help.html`](../../prototype/file_scheduler/schedule_dependency_help.html)  
> **Rama:** `diseno_desarrollo_FILE_SCHEDULER`

---

## Propósito

```text
Termina Job A / pipeline run A  (éxito según regla)
  → Este plan (destino M3) se encola
  → trigger_source=dependency
  → parent_job_id o parent_pipeline_run_id
```

Esto **no** es el diseñador de pasos de File Pipeline. El orquestador ya encadena Clean → Gate → … Aquí el Scheduler une **dos runners ya existentes** (“cuando Gate de ventas ACCEPTED → Pipe v5”) sin redibujar la cadena.

**No cubre:** cron (M2), destino (M3), worker de reloj (M4), Watch, bucles de N planes (MVP: un padre, sin grafo).

---

## Disparador: reloj o dependencia

Un plan tiene un `trigger_mode` (MVP: **uno**, no ambos a la vez).

| `trigger_mode` | Cuándo dispara | Para Activar / Reanudar |
|----------------|----------------|-------------------------|
| `time` (default) | Ventanas M2 | Destino M3 **y** programación M2 |
| `dependency` | Termina el padre (este módulo) | Destino M3 **y** padre válido. M2 no es obligatorio |

El worker de cron (M4) **no** evalúa planes `dependency`. El encolado “tras A” es otro camino (hook al terminar el Job/pipeline), misma cola y misma política de solape (M5) sobre **este** plan.

---

## Acción en el hub

Enlace **Dependencia** → esta pantalla (PA/ED). GE/CO: lectura.

Guardar **no** cambia `status`. Auditoría: `schedule.updated` (`trigger_mode`, padre, condición).

Si pasa de `time` a `dependency`, el cron guardado en M2 queda inerte (no se borra). Si vuelve a `time`, se exige M2 válido para Activar.

---

## Modelo (MVP)

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `trigger_mode` | Sí | `time` · `dependency` |
| `parent_kind` | Si `dependency` | `job` · `pipeline` |
| `parent_project_id` | Si padre = job | Proyecto de la **misma compañía**. Cualquier run publicado de ese proyecto que cumpla la condición. |
| `parent_pipeline_id` | Si padre = pipeline | Pipeline de la misma compañía. |
| `on_parent` | Si `dependency` | `succeeded` (**default**) · `accepted` (p. ej. Gate ACCEPTED) · `completed` (cualquier terminal distinto de cancelado — **no** recomendado) |

Un solo padre. Sin “A o B”. Sin depender de **este mismo** plan (el destino M3 no puede ser el padre: bucle inmediato).

**Identidad del fire:** `schedule_id` + `parent_job_id` o `parent_pipeline_run_id` = **un** encolado. El mismo run padre no dispara dos veces.

`scheduled_for` en actividad: instante en que el padre **terminó** (zona del plan si hay; si no, IANA de compañía).

Entrada del Job B: la de M3 (Watch / artifact / none). No se copia el archivo del padre en MVP (handoff `artifact_ref` = mejora de runners).

---

## Condición del padre

| `on_parent` | Dispara este plan si el padre… |
|-------------|-------------------------------|
| `succeeded` | Terminó OK (job success / pipeline completed sin fallo) |
| `accepted` | Gate (u homólogo) en veredicto aceptado. Si el padre no es Gate, no usar; validar al guardar. |
| `completed` | Llegó a terminal (incluye fallo). **Fuera del default**; riesgo de encadenar errores. |

Si el padre **falla** y la regla es `succeeded` → no dispara. No hay reintento automático de B; eso es M4/reintento del run.

Actor: `system:scheduler`. `trigger_source=dependency`. Campos Pipeline: `parent_job_id` / `parent_pipeline_run_id`.

---

## Relación con M4 / M5

| Tema | Regla |
|------|--------|
| Plan `inactive` / `archived` | No encola B (`schedule_paused`) |
| Solape | Misma `overlap_policy` si B anterior sigue vivo |
| Destino sin publicada / sin archivo | No encola; `schedule_no_published_target` / `schedule_missing_input` |
| No es misfire de cron | No aplica `schedule_misfire` de ventana horaria |

---

## Validación

| `error_code` (tentativo) | Cuándo |
|--------------------------|--------|
| `validation_required` | `dependency` sin padre |
| `schedule_dependency_cycle` | Padre = destino de este plan (mismo proyecto o mismo pipeline) |
| `schedule_dependency_cross_tenant` | Padre de otra compañía (404 opaco) |
| `schedule_forbidden` | GE/CO guarda |
| `schedule_no_published_target` | Padre pipeline no operativo (al guardar, si se puede saber) |

---

## Autorización

PA/ED: editar. GE/CO: ver. El fire no bypasea permisos del **destino** (M3 / producto §9).

---

## Fuera de alcance

- Grafos A→B→C de varios planes (componer con varios schedules o usar File Pipeline).  
- Diseñador de pasos.

---

## Criterio de aceptación (diseño)

- [x] `trigger_mode` time vs dependency; Activar exige M3 + (M2 **o** padre).  
- [x] Un padre; sin bucle destino=padre.  
- [x] Idempotencia por run padre.  
- [x] `trigger_source=dependency` en el run delegado.  
- [x] Prototipos HTML.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) | §2 · §7-B |
| [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) | §7.1-B `dependency` |
| [`sch_cron.md`](sch_cron.md) | Reloj si `time` |
| [`sch_target.md`](sch_target.md) | Qué se encola (B) |
| [`sch_tick.md`](sch_tick.md) | Actividad; no el worker de cron |
| [`sch_lifecycle.md`](sch_lifecycle.md) | Activar / Reanudar |
| [`README.md`](README.md) | Índice |
