# Módulo 8 — Errores (`schedule_*` y capas)

Catálogo de **`error_code`** / **`user_message`** del Scheduler. El código no se muestra al usuario. Los fallos de Gate/Pipe/pasos de pipeline **no** se duplican: se **enlazan**.

> **Estado:** **Implementado (M8)** (`apps.file_scheduler.services.schedule_errors` · `templates/file_scheduler/errors/` · volcado en UI_MESSAGES §3.18)  
> **Producto:** [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) §8  
> **Índice:** [`README.md`](README.md)  
> **Previo:** auditoría [`sch_audit.md`](sch_audit.md)  
> **Siguiente:** notificaciones [`sch_notify.md`](sch_notify.md)  
> **UI_MESSAGES:** [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) §3.18  
> **Prototipos:** catálogo [`../../prototype/file_scheduler/schedule_errors.html`](../../prototype/file_scheduler/schedule_errors.html) · ayuda [`schedule_errors_help.html`](../../prototype/file_scheduler/schedule_errors_help.html)  
> **Rama:** `diseno_desarrollo_FILE_SCHEDULER`

---

## Propósito

Servicios: `ok` / `error_code` / `user_message` / `errors` (campos). Logs técnicos: `logger.exception`, no en la UI.

```text
Capa 1  Auth / tenant     → 404 opaco (no schedule_*)
Capa 2  CRUD / validación → inline ± un modal genérico
Capa 3  Tick (antes de encolar) → Actividad + auditoría; códigos schedule_*
Capa 4  Job / pipeline    → historial de la app o pipeline_run_id
```

Paridad PLATFORM API §9 y producto §8.

---

## Canales (UI_MESSAGES)

| Situación | Canal |
|-----------|--------|
| Campo inválido (cron, padre, proyecto) | **Inline** + opcional `messages.error` genérico |
| Permiso / no se puede activar | **Modal** `messages.error` |
| Tick omitido o fallido | **Actividad** + **Auditoría** (no modal en cada slot) |
| Otra compañía / no existe | **404 opaco** |
| Éxito CRUD | `messages.success` + PRG |

Prototipos actuales pueden usar `alert()`; al implementar: `dwShowMessage` / `#dw-msg-modal`. Sin `confirm()` nativo en producto (excepto prototipo).

---

## Capa 1 — Auth / tenant

No inventar `schedule_*`. Compañía inactiva o plan ajeno → no listar, detalle 404.

---

## Capa 2 — CRUD y validación

| `error_code` | Cuándo | `user_message` (tentativo) |
|--------------|--------|----------------------------|
| `validation_required` | Falta campo obligatorio | Complete los campos obligatorios. |
| `schedule_slug_taken` | Slug duplicado en la compañía | Ese código ya existe en la compañía. |
| `schedule_forbidden` | GE/CO guarda o sin rol | No tiene permiso para cambiar este plan. |
| `schedule_cron_invalid` | Expresión o preset inválido | La programación no es válida. Consulte la Ayuda. |
| `schedule_timezone_invalid` | IANA desconocida | La zona horaria no es válida. |
| `schedule_no_published_target` | Destino sin publicada / pipeline no activo (al guardar o al fire) | El destino no tiene una versión publicada operativa. |
| `schedule_missing_input` | Job de archivo sin Watch/artifact | Falta el archivo de entrada. No se puede disparar sin Watch o una referencia. |
| `schedule_target_cross_tenant` | Destino de otra company | (404 opaco; no este texto) |
| `schedule_dependency_cycle` | Padre = destino | El padre no puede ser el mismo destino del plan. |
| `schedule_dependency_cross_tenant` | Padre de otra company | (404 opaco) |
| `schedule_incomplete` | Activar/Reanudar sin M3 o sin (M2 o M6) | Complete el destino y el disparador (horario o dependencia) para activar. |

Éxitos (PRG): *Plan creado correctamente.* · *Programación guardada.* · *Destino guardado.* · *Política de solape guardada.* · *Disparador guardado.* · *Plan pausado.* / *Plan reanudado.* / *Plan archivado.*

---

## Capa 3 — Tick (Scheduler, antes de encolar)

Aparecen en Actividad (código) y Auditoría (`tick_skipped` / `tick_failed`). El usuario **no** ve el `error_code` como título; sí puede verse en columna técnica del prototipo.

| `error_code` | Evento | `user_message` (tentativo) |
|--------------|--------|----------------------------|
| `schedule_paused` | no fire | El plan no está activo. |
| `schedule_overlap_skip` | `tick_skipped` | Se omitió este horario porque el run anterior sigue en curso. |
| `schedule_misfire` | skipped/failed | No se ejecutó a tiempo (el programador no estaba disponible). Se sigue con la próxima ventana. |
| `schedule_enqueue_failed` | `tick_failed` | No se pudo encolar el Job. Inténtelo más tarde o revise la cola. |
| `schedule_artifact_not_found` | `tick_failed` | No se encontró el archivo del artifact en storage. Verifique el hash. |
| `schedule_runner_unsupported` | `tick_failed` | Este tipo de destino aún no se ejecuta desde el Scheduler. |
| `schedule_no_published_target` | `tick_failed` | (mismo texto capa 2) |
| `schedule_missing_input` | `tick_failed` | (mismo texto capa 2) |

`schedule_overlap_skip` **no** es un fallo de formulario: es política M5.

---

## Capa 4 — Ejecución delegada

**Prohibido** crear `schedule_gate_rejected` u homólogos. Abrir `job_id` / `pipeline_run_id`. Códigos de la app o `pipeline_*`.

---

## Qué no mostrar

SQL, trazas, tokens, contenido de archivo, nombres internos de cola Railway en el `user_message` (sí en log).

---

## Fuera de alcance

- Implementar el mapa Python en `apps.core` (el mapa vive en `apps.file_scheduler.services.schedule_errors`).  
- Notificaciones (M9).

---

## Criterio de aceptación (diseño)

- [x] Cuatro capas; capa 4 solo enlace.  
- [x] Tabla `error_code` ↔ `user_message` en este doc.  
- [x] Prototipo catálogo (búsqueda / filtro por capa).  
- [x] Código Django + UI_MESSAGES §3.18.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) | §8 |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Canales; destino al implementar |
| [`sch_tick.md`](sch_tick.md) · [`sch_lifecycle.md`](sch_lifecycle.md) | Origen de códigos |
| [`README.md`](README.md) | Índice |
