# Módulo 9 — Notificaciones (correo / webhook)

Avisar a personas o a un sistema cuando **falla la ingestión**, el **fire al llegar**, o (si aplica) el **Job/pipeline** encolado por Watch. No adjunta ni registra el contenido del archivo.

> **Estado:** **Diseño M9** (spec + prototipos HTML); implementación Django / Resend pendiente de OK  
> **Producto:** [`../FILE_WATCH.md`](../FILE_WATCH.md) §2  
> **Índice:** [`README.md`](README.md)  
> **Previo:** errores [`wach_errors.md`](wach_errors.md)  
> **Siguiente:** integración [`wach_integration.md`](wach_integration.md)  
> **Correo:** Resend (`RESEND_API_KEY`) — convención de plataforma.  
> **Prototipos:** [`../../prototype/file_watch/watch_notify.html`](../../prototype/file_watch/watch_notify.html) · [`watch_notify_help.html`](../../prototype/file_watch/watch_notify_help.html)  
> **Rama:** `diseno_desarrollo_FILE_WATCH`

---

## Propósito

```text
intake_failed  |  fire_failed  |  run delegado failed
  → ¿la bandeja pide aviso?
  → correo (Resend) y/o webhook HTTPS
  → watch.notify_sent (auditoría: destinatario tipo, resultado, timestamp)
```

**No cubre:** plantillas de marketing, SMTP propio, cuerpo con celdas, avisos del **tick del Scheduler** (eso es M9 del plan: [`sch_notify.md`](../definition_app_FILE_SCHEDULER/sch_notify.md)).

Default MVP: **avisos apagados**. Activar la bandeja **no** exige esta pantalla.

---

## Qué dispara un aviso

| Evento | ¿Avisa? (si está encendido) |
|--------|------------------------------|
| `watch.batch_intake_failed` | Sí, si `notify_on` incluye `intake` |
| `watch.fire_failed` | Sí, si incluye `fire` |
| Job/pipeline encolado por Watch (`on_arrival`) en estado **failed** | Sí, si incluye `run` |
| `watch.batch_skipped` (duplicado / cuota) | **No** por default. Opcional `notify_on_skip` (off) |
| `watch.batch_ingested` / claim OK / fire OK | No |
| CRUD (pausar, editar origen…) | No |
| Tick del Scheduler falló (`schedule_missing_input`, …) | **No aquí** — avisos del **plan** |

Un aviso por evento de lote/fire (idempotente: no reenviar el mismo `batch_id` + `error_code`). Fallo de Resend ≠ reintento de intake.

---

## Modelo

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `notify_enabled` | Sí | Default `false` |
| `notify_on_intake_failed` | Si enabled | Default true al encender |
| `notify_on_fire_failed` | Si enabled | Default true al encender |
| `notify_on_run_failed` | Si enabled | Default true; solo relevante si `fire_mode=on_arrival` |
| `notify_on_skip` | No | Default false (duplicado/cuota) |
| `notify_user_ids` | Si enabled y canal email | Miembros **de la bandeja** (UF). Email = cuenta DW, no libreta suelta |
| `notify_webhook_url` | No | HTTPS. Vacío = solo correo. Firma = contrato PLATFORM API |
| `notify_channel` | Sí si enabled | `email` · `webhook` · `both` |

Cuerpo correo: código de bandeja, filename si hay, `error_code` Watch o “el Job falló” + enlace a lote/run. **Sin** adjuntos ni filas.

Webhook: `watch_id`, `event`, `occurred_at`, `batch_id`, `error_code` opcionales, `job_id` / `pipeline_run_id` si hay. Sin bytes.

---

## Acción en el hub

**Avisos** (definición, paso 6 del rail). PA/ED editan. GE/CO leen. Guardar no cambia `status`.

Auditoría: `watch.idempotency_updated`-style → `watch.notify_updated` (canales) y `watch.notify_sent` por envío ([`wach_audit.md`](wach_audit.md)).

Fallo al enviar el aviso **no** reintenta el intake ni el Job.

---

## Quién recibe el correo

1. Debe ser **miembro de la bandeja** (pantalla Miembros).  
2. En Avisos se **marcan** quiénes reciben. Resend usa el email de esa cuenta.  
3. Webhook = sistema (ERP), URL en la misma pantalla.

Si falta alguien → Miembros, luego tildar en Avisos.

---

## Validación

| `error_code` | Cuándo |
|--------------|--------|
| `validation_required` | Avisos on y ni miembro ni webhook |
| `watch_notify_webhook_invalid` | No HTTPS / vacío inválido |
| `watch_forbidden` | GE/CO guarda |

Éxito: *Avisos guardados correctamente.*

---

## Autorización

PA/ED: editar. GE/CO: ver. Matriz M1.

---

## Relación con Scheduler notify

| Watch M9 | Scheduler M9 |
|----------|--------------|
| Fallos de **bandeja** (intake/fire) | Fallos de **tick** / run del plan |
| `pending_only`: sin fire → no hay `notify_on_fire`; el plan avisa si el tick falla | Plan con `watch_id` usa sus propios avisos |

Pueden coexistir: Watch avisa intake fallido; plan avisa `schedule_missing_input` si no hay lote.

---

## Fuera de alcance

- Duplicar `pa_webhooks.md`.  
- Avisar cada skip por default.  
- Implementar Resend hasta «Desarrolla el módulo».

---

## Criterio de aceptación del módulo (diseño)

- [x] Default off; triggers intake / fire / run / skip opcional.  
- [x] Destinatarios = miembros de bandeja + webhook HTTPS.  
- [x] Sin bytes de archivo; `watch.notify_sent`.  
- [x] Frontera con avisos del plan.  
- [x] Prototipos + ayuda + hub.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`wach_errors.md`](wach_errors.md) | Códigos en el aviso |
| [`wach_audit.md`](wach_audit.md) | `watch.notify_sent` |
| [`../definition_app_FILE_SCHEDULER/sch_notify.md`](../definition_app_FILE_SCHEDULER/sch_notify.md) | Hermano |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Textos al implementar |
