# Módulo 9 — Notificaciones (correo / webhook)

Avisar a personas o a un sistema cuando el **tick falla al encolar** o cuando el **Job/pipeline delegado falla**. No adjunta ni registra el contenido del archivo.

> **Estado:** **Implementado (M9)** (`apps.file_scheduler.services.schedule_notify` · `…/avisos/` · Resend vía `email_delivery`)  
> **Producto:** [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) §10 notificaciones · Pipeline §7.1-D  
> **Índice:** [`README.md`](README.md)  
> **Previo:** errores [`sch_errors.md`](sch_errors.md)  
> **Siguiente:** integración [`sch_integration.md`](sch_integration.md)  
> **Correo:** Resend (`RESEND_API_KEY`) — convención de plataforma.  
> **Prototipos:** [`../../prototype/file_scheduler/schedule_notify.html`](../../prototype/file_scheduler/schedule_notify.html) · ayuda [`schedule_notify_help.html`](../../prototype/file_scheduler/schedule_notify_help.html)  
> **Rama:** `diseno_desarrollo_FILE_SCHEDULER`

---

## Propósito

```text
tick_failed  o  run delegado failed
  → ¿el plan pide aviso?
  → correo (Resend) y/o webhook HTTPS
  → schedule.notify_sent (auditoría: destinatario tipo, resultado, timestamp)
```

**No cubre:** diseño de plantillas de marketing, SMTP propio, cuerpo con celdas del archivo, reintentos infinitos de webhook (heredar política PLATFORM API / Pipeline).

Default MVP: **avisos apagados**. Activar el plan no exige esta pantalla.

---

## Qué dispara un aviso

| Evento | ¿Avisa? (si está encendido) |
|--------|------------------------------|
| `schedule.tick_failed` (no encoló: missing_input, enqueue_failed, no_published_target, …) | Sí, si `notify_on` incluye `tick` |
| Job/pipeline delegado en estado **failed** (capa 4) | Sí, si `notify_on` incluye `run` |
| `tick_skipped` (solape, misfire de política skip) | **No** en default. Opcional `notify_on_skip` (off) |
| `tick_enqueued` con Job OK | No |
| CRUD (pausar, editar) | No |

Un aviso por **evento de tick** (idempotente: no reenviar el mismo `tick_id` / `job_id` fallido). Reintento de envío de correo ≠ nuevo tick.

---

## Modelo

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `notify_enabled` | Sí | Default `false` |
| `notify_on_tick_failed` | Si enabled | Default true si enciende avisos |
| `notify_on_run_failed` | Si enabled | Default true si enciende avisos |
| `notify_on_skip` | No | Default false |
| `notify_user_ids` | Si enabled y canal email | UF **miembros del plan** (misma compañía). El correo es el del usuario en DynamicWorkspace, no una libreta suelta. Se eligen en **Avisos**; se dan de alta en **Miembros**. |
| `notify_webhook_url` | No | HTTPS. Vacío = solo correo. Firma: reutilizar contrato de webhooks de API (no inventar HMAC aquí) |
| `notify_channel` | Sí si enabled | `email` · `webhook` · `both` |

Cuerpo del correo (negocio): código del plan, `scheduled_for` o padre, `error_code` de **Scheduler** o “el Job/pipeline falló” + enlace al run. **Sin** filas ni adjuntos.

Webhook payload: `schedule_id`, `event`, `occurred_at`, `job_id` / `pipeline_run_id` opcionales, `error_code` si es tick. Sin bytes de archivo.

---

## Acción en el hub

**Avisos** (definición). PA/ED editan. GE/CO leen. Guardar no cambia `status`. Auditoría `schedule.updated` (canales) y `schedule.notify_sent` por cada envío (éxito o fallo de Resend/HTTP, sin PII de celdas).

Fallo al enviar el aviso **no** reintenta el Job. Se audita; el tick ya está fallido u omitido.

---

## Validación

| `error_code` | Cuándo |
|--------------|--------|
| `validation_required` | Avisos on y ni un miembro tildado ni webhook |
| `schedule_notify_email_invalid` | Dirección mal formada |
| `schedule_notify_webhook_invalid` | No HTTPS / host vacío |
| `schedule_forbidden` | GE/CO guarda |

---

## Autorización

## Quién recibe el correo

1. El usuario debe ser **miembro del plan** (pantalla **Miembros**: se invita un UF de ACME y se le asigna PA/ED/GE/CO).  
2. En **Avisos** se **marcan** qué miembros reciben el fallo. Resend usa el **email de esa cuenta UF** (el de la compañía), no un texto libre tipo `ops@…` en MVP.  
3. El **webhook HTTPS** no es una persona: es un sistema (ERP, cola). Se configura la URL en la misma pantalla Avisos.

No hay un “usuario de correo” aparte del UF. Si falta alguien, se agrega en Miembros y luego se tilda en Avisos.

---

## Fuera de alcance

- Duplicar `pa_webhooks.md` (se reutiliza HMAC `X-Platform-Signature`).  
- Avisar a cada overlap skip por defecto.

---

## Criterio de aceptación (diseño)

- [x] Default off; tick_failed y run_failed configurables.  
- [x] Sin contenido de archivo en correo/log de notify.  
- [x] `schedule.notify_sent` en M7.  
- [x] Prototipo HTML.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) | §10 |
| [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) | §7.1-D notificaciones |
| [`../definition_app_PLATFORM_API/pa_webhooks.md`](../definition_app_PLATFORM_API/pa_webhooks.md) | Firma webhook |
| [`sch_audit.md`](sch_audit.md) | `notify_sent` |
| [`sch_errors.md`](sch_errors.md) | Capa 3 vs 4 |
| [`README.md`](README.md) | Índice |
