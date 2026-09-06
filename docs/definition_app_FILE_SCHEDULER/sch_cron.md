# Módulo 2 — Programación (cron / calendario)

Expresión de **cuándo** dispara el plan. No define destino (M3) ni ejecuta el Job (M4).

> **Estado:** **M2 implementado** (programación Django)  
> **Producto:** [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) §3 · §5 · §10 (ventana / `scheduled_for`)  
> **Índice:** [`README.md`](README.md)  
> **Previo:** [`sch_lifecycle.md`](sch_lifecycle.md)  
> **Siguiente:** destino [`sch_target.md`](sch_target.md)  
> **Prototipos:** [`../../prototype/file_scheduler/schedule_cron.html`](../../prototype/file_scheduler/schedule_cron.html) · ayuda [`schedule_cron_help.html`](../../prototype/file_scheduler/schedule_cron_help.html) (mismo patrón que `templates/platform_api/clients/create_help.html`)  
> **Rama:** `diseno_desarrollo_FILE_SCHEDULER`

---

## Propósito

El usuario declara el **reloj** del plan: frecuencia, hora y zona. El worker (M4) evaluará esa definición; este módulo solo **guarda y valida** el calendario.

```text
Plan (M1)
  → Programación (este módulo): cron / preset + timezone
  → Destino (M3): qué Job o pipeline
  → Tick (M4): a esa hora, encolar
```

**No cubre:** Watch (llegada de archivo), destino IFS, solape (M5), “tras Job A” (M6), disparo real.

---

## Acción en el hub

Enlace **Programación (cron)** del rail → pantalla de este módulo (PA/ED). GE/CO: solo lectura (expresión y próximos slots, sin guardar).

Guardar **no** cambia `status` (sigue En proceso / Activo / Inactivo). Sí habilita el requisito M2 para **Activar** / **Reanudar** (junto con M3).

Editar un plan `active` actualiza el cron; el próximo tick usa la nueva expresión. No cancela un Job ya encolado. Auditoría: `schedule.updated` (diff de cron/timezone).

---

## Modelo de programación (MVP)

Una sola regla por plan (no calendarios múltiples en MVP).

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `schedule_kind` | Sí | `daily` · `weekdays` · `weekly` · `monthly` · `cron` |
| `time_local` | Sí si kind ≠ solo cron crudo | Hora `HH:MM` en la zona del plan |
| `day_of_week` | Si `weekly` | Un día: lun–dom (cron 0=dom … 6=sáb; UI en español) |
| `monthly_mode` | Si `monthly` | `last_day` (**default**) · `specific` |
| `day_of_month` | Si `monthly` + `specific` | 1–31. Si el mes no tiene ese día → **último día de ese mes** |
| `cron_expr` | Si `kind=cron` | 5 campos (min hora día-mes mes día-sem). Sin segundos. |
| `timezone` | Sí | Default compañía (p. ej. `America/Caracas`). IANA. |

Persistencia canónica: el worker puede materializar siempre un `cron_expr` interno aunque la UI muestre un preset.

### Presets (UI)

| `schedule_kind` | Significado | Ejemplo interno |
|-----------------|-------------|-----------------|
| `daily` | Todos los días a `time_local` | `30 2 * * *` (02:30) |
| `weekdays` | Lunes–viernes a `time_local` | `0 6 * * 1-5` |
| `weekly` | Un día de la semana a `time_local` | `0 2 * * 1` (lunes 02:00) |
| `monthly` | Último día **o** día N (1–31, clamp al último del mes) | Worker: no un cron 5 campos puro si es último día; regla de calendario |
| `cron` | Expresión avanzada | Lo que valide el parser |

**Fuera de MVP (producto §3 “otras”):** calendario de feriados de la compañía, ventanas de mantenimiento. **Último día del mes** sí entra en este módulo (`monthly_mode=last_day`).

---

## Próximos ticks (preview)

La pantalla muestra las **próximas 3 ventanas** (`scheduled_for` en timezone del plan) en solo lectura.

- Si la expresión es inválida → no hay preview; error de campo.  
- El preview **no** dispara. M4 usa la misma función de cálculo.

Clave de idempotencia (producto §10): `schedule_id` + `scheduled_for` (instante de la ventana).

---

## Validación

| `error_code` (tentativo) | Cuándo |
|--------------------------|--------|
| `validation_required` | Falta hora o expresión |
| `schedule_cron_invalid` | Parser rechaza `cron_expr` o combinación preset. Prototipo: 5 campos; cada uno `*`, número, lista (`1,15`), rango (`1-5`) o paso (`*/15`) en su rango (min 0–59, hora 0–23, día-mes 1–31, mes 1–12, día-sem 0–6). Bloquea guardar; alerta + inline y enlace a Ayuda. |
| `schedule_forbidden` | GE/CO intenta guardar |
| `schedule_timezone_invalid` | Zona IANA desconocida |

Servicio: `ok` / `error_code` / `user_message`. Errores **inline**, no solo modal.

---

## Autorización

PA/ED: editar. GE/CO: ver. Misma matriz M1.

---

## Relación con el tick

| Este módulo | M4 Tick |
|-------------|---------|
| Define cron + TZ | Evalúa y encola |
| Preview de slots | Fire real + misfire |
| No habla de archivo | `schedule_missing_input` si M3 no resuelve entrada |

---

## Auditoría

`schedule.updated` con snapshot `schedule_kind`, `cron_expr`, `timezone`, `time_local`. No eventos de tick aquí.

---

## Fuera de alcance

- Worker Railway, cola, misfire.  
- Destino Job/pipeline.  
- Dependencias “tras A”.

---

## Criterio de aceptación (diseño)

- [x] Presets diario / laborables / **semanal (día de la semana)** / mensual (**último día** o día 1–31 con clamp) + cron avanzado.  
- [x] Timezone IANA; default de compañía.  
- [x] Preview de 3 próximos `scheduled_for`.  
- [x] Validación `schedule_cron_invalid`.  
- [x] No cambia status al guardar.  
- [x] Prototipos HTML (Simple Browser: `/prototype/file_scheduler/`).  
- [x] Ayuda de programación: propósito, campos (obligatorio / función / valores), presets, mensual, cron 5 campos, acciones.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) | §3 · §5 · §10 |
| [`sch_lifecycle.md`](sch_lifecycle.md) | Hub; Activar exige M2+M3 |
| [`README.md`](README.md) | Índice |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Textos al implementar |
