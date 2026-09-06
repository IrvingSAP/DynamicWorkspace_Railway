# Módulo 8 — Errores (`watch_*` y capas)

Catálogo de **`error_code`** / **`user_message`** de File Watch. El código no se muestra al usuario como título. Los fallos de Gate/Pipe/pasos de pipeline **no** se duplican: se **enlazan**. Los fallos del tick del plan siguen siendo `schedule_*` ([`sch_errors.md`](../definition_app_FILE_SCHEDULER/sch_errors.md)).

> **Estado:** **Diseño M8** (spec + prototipos HTML); mapa Python / UI_MESSAGES al implementar  
> **Producto:** [`../FILE_WATCH.md`](../FILE_WATCH.md) §7  
> **Índice:** [`README.md`](README.md)  
> **Previo:** auditoría [`wach_audit.md`](wach_audit.md)  
> **Siguiente:** notificaciones [`wach_notify.md`](wach_notify.md)  
> **UI_MESSAGES:** [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) (sección Watch al implementar)  
> **Prototipos:** [`../../prototype/file_watch/watch_errors.html`](../../prototype/file_watch/watch_errors.html) · [`watch_errors_help.html`](../../prototype/file_watch/watch_errors_help.html)  
> **Rama:** `diseno_desarrollo_FILE_WATCH`

---

## Propósito

Servicios: `ok` / `error_code` / `user_message` / `errors` (campos). Logs técnicos: `logger.exception`, no en la UI.

```text
Capa 1  Auth / tenant          → 404 opaco (no watch_*)
Capa 2  CRUD / config          → inline ± modal genérico
Capa 3  Intake / fire / cuota → Lotes + Auditoría; códigos watch_*
Capa 4  Job / pipeline         → historial de la app o pipeline_run_id
```

Paridad Scheduler M8 y PLATFORM API §9.

---

## Canales

| Situación | Canal |
|-----------|--------|
| Campo inválido (slug, SFTP, política) | **Inline** + opcional `messages.error` genérico |
| Permiso / no se puede activar | **Modal** `messages.error` |
| Lote omitido / falló intake / fire | **Lotes** + **Auditoría** (no modal en cada llegada) |
| Otra compañía / no existe | **404 opaco** |
| Éxito CRUD / config | `messages.success` + PRG |

Prototipos pueden usar `alert()`; al implementar: `dwShowMessage` / `#dw-msg-modal`.

---

## Capa 1 — Auth / tenant

No inventar `watch_*`. Compañía inactiva o bandeja ajena → no listar, detalle 404.

---

## Capa 2 — CRUD y configuración

| `error_code` | Cuándo | `user_message` (tentativo) |
|--------------|--------|----------------------------|
| `validation_required` | Falta campo obligatorio | Complete los campos obligatorios. |
| `watch_slug_taken` | Slug duplicado en la compañía | Ese código de bandeja ya existe en la compañía. |
| `watch_forbidden` | Sin rol / GE·CO guarda / UF crea | No tiene permiso para cambiar esta bandeja. |
| `watch_incomplete` | Activar/Reanudar sin origen (o sin ruta si fire al llegar) | Complete el origen (y el enrutado si dispara al llegar) para activar. |
| `watch_source_invalid` | Kind/campos/patrón inválidos | La configuración del origen no es válida. Consulte la Ayuda. |
| `watch_secret_missing` | SFTP sin secreto | Indique la credencial del origen SFTP. |
| `watch_sftp_unreachable` | Probar conexión falló | No se pudo conectar al SFTP. Revise host, puerto y credencial. |
| `watch_no_published_target` | Job/pipeline sin publicada (guardar ruta o activar) | El destino no tiene una versión publicada operativa. |
| `watch_fire_route_conflict` | `on_arrival` + enrutado Diferir | «Al llegar» no es compatible con enrutado Diferir. Elija Job/Pipeline o cambie el disparo. |
| `watch_route_cross_tenant` | Destino otra company | (404 opaco) |

Éxitos (PRG): *Bandeja creada correctamente.* · *Origen guardado correctamente.* · *Política de intake guardada.* · *Enrutado guardado correctamente.* · *Disparo guardado correctamente.* · *Política de idempotencia guardada correctamente.* · *Bandeja pausada.* / *reanudada.* / *archivada.*

---

## Capa 3 — Intake / fire / cuota (runtime)

Aparecen en Lotes (estado + código) y Auditoría. El usuario **no** ve el `error_code` como título de página; columna técnica en prototipo/ops.

| `error_code` | Evento típico | `user_message` (tentativo) |
|--------------|---------------|----------------------------|
| `watch_intake_unstable` | `batch_intake_failed` | El archivo seguía cambiando y no se pudo ingerir. |
| `watch_intake_too_large` | `batch_intake_failed` | El archivo supera el tamaño máximo permitido. |
| `watch_intake_store_failed` | `batch_intake_failed` | No se pudo guardar el archivo en storage. Inténtelo más tarde. |
| `watch_intake_hash_failed` | `batch_intake_failed` | No se pudo calcular el hash del archivo. |
| `watch_duplicate_content` | `batch_skipped` | Se omitió la llegada: el contenido ya fue ingerido en esta bandeja. |
| `watch_quota_pending` | `batch_skipped` | Se omitió: hay demasiados lotes pendientes en la bandeja. |
| `watch_quota_daily` | `batch_skipped` | Se omitió: se alcanzó el máximo de llegadas del día. |
| `watch_quota_bytes` | `batch_skipped` | Se omitió: se alcanzó el máximo de volumen del día. |
| `watch_fire_failed` | `fire_failed` | No se pudo encolar el Job al llegar el archivo. |
| `watch_no_published_target` | `fire_failed` | (mismo texto capa 2) |
| `watch_inactive` | `fire_skipped` | La bandeja no está activa; no se dispara. |

**Frontera Scheduler:** si el plan pide lote y no hay `pending` → **`schedule_missing_input`** (capa tick del plan), no un `watch_*`. Si el hash del lote no está en storage → **`schedule_artifact_not_found`**.

---

## Capa 4 — Ejecución delegada

**Prohibido** crear `watch_gate_rejected` u homólogos. Abrir `job_id` / `pipeline_run_id`. Códigos de la app o `pipeline_*`.

---

## Qué no mostrar

SQL, trazas, tokens, password, contenido de archivo, nombres internos de cola Railway en el `user_message` (sí en log).

---

## Fuera de alcance

- Implementar `schedule_errors`-style module en Django (al «Desarrolla el módulo»).  
- Volcado definitivo a UI_MESSAGES (misma fase).  
- Notificaciones (M9).

---

## Criterio de aceptación del módulo (diseño)

- [x] Cuatro capas; capa 4 solo enlace.  
- [x] Tabla `error_code` ↔ `user_message`.  
- [x] Frontera explícita con `schedule_missing_input`.  
- [x] Prototipo catálogo (filtro por capa).

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`wach_lifecycle.md`](wach_lifecycle.md) … [`wach_idempotency.md`](wach_idempotency.md) | Orígenes de códigos |
| [`../definition_app_FILE_SCHEDULER/sch_errors.md`](../definition_app_FILE_SCHEDULER/sch_errors.md) | Hermano; missing input |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Catálogo producto |
| [`wach_notify.md`](wach_notify.md) | Aviso al fallar |
