# Módulo 5 — Solape e idempotencia de ventana

Qué hace el worker si llega un tick y el Job/run **anterior del mismo plan sigue vivo**, y cómo se evita **duplicar** el mismo `scheduled_for`.

> **Estado:** **Implementado (M5)** (`apps.file_scheduler`: `overlap_policy`, UI Solape, worker skip/queue/cancel)  
> **Producto:** [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) §10 (solape · idempotencia)  
> **Índice:** [`README.md`](README.md)  
> **Previo:** tick [`sch_tick.md`](sch_tick.md)  
> **Siguiente:** dependencia [`sch_dependency.md`](sch_dependency.md)  
> **Prototipos:** [`../../prototype/file_scheduler/schedule_overlap.html`](../../prototype/file_scheduler/schedule_overlap.html) · ayuda [`schedule_overlap_help.html`](../../prototype/file_scheduler/schedule_overlap_help.html)  
> **Rama:** `diseno_desarrollo_FILE_SCHEDULER`

---

## Propósito

Dos reglas distintas:

| Problema | Pregunta | Este módulo |
|----------|----------|-------------|
| **Idempotencia de ventana** | ¿Ya se fireó este `scheduled_for`? | Un slot = un fire. Siempre. |
| **Solape** | El run de una ventana **anterior** ¿sigue vivo? | Política del plan: skip (MVP) / queue / cancel-previous |

No define el cron (M2), el destino (M3) ni el worker (M4): M4 **aplica** la política aquí guardada.

```text
Slot nuevo (M2)
  → ¿Este scheduled_for ya tiene fire? → no duplicar
  → ¿Hay run vivo del mismo plan? → overlap_policy (este módulo)
  → Si pasa: encolar (M4)
```

---

## Acción en el hub

Enlace **Solape** (definición, junto a Programación y Destino) → pantalla de este módulo (PA/ED). GE/CO: solo lectura.

Guardar **no** cambia `status`. No es requisito de Activar (M2+M3 sí lo son): si no se eligió, aplica el **default Skip**.

Editar un plan `active` cambia la política del **próximo** tick. No reescribe ticks ya omitidos ni aborta un run en curso (salvo que la nueva política sea cancel-previous **en el siguiente** solape).

Auditoría: `schedule.updated` (diff de `overlap_policy`).

---

## Idempotencia de ventana (siempre)

Análogo a `Idempotency-Key` (PLATFORM API §11).

| Regla | Detalle |
|-------|---------|
| Clave | `schedule_id` + `scheduled_for` |
| Efecto | El worker no crea dos fires para el mismo slot |
| Reintento | **Nuevo** run (`retry_of_run_id`) con otra ventana o clave explícita; no reescribir el tick |

Esto **no** es configurable en UI. No se confunde con solape: dos ventanas distintas (02:00 de ayer vs 02:00 de hoy) son dos slots; el solape pregunta si el Job de ayer **aún corre**.

---

## Política de solape (`overlap_policy`)

Un valor por plan. **Default MVP: `skip`.**

| Valor | UI | Si el run anterior sigue vivo | Auditoría |
|-------|-----|-------------------------------|-----------|
| `skip` | Omitir (recomendado) | No encolar el slot nuevo. Tick **Omitido**, `schedule_overlap_skip` | `schedule.tick_skipped` |
| `queue` | Encolar detrás | Encolar el slot nuevo igualmente (puede haber más de un run del plan) | `schedule.tick_enqueued` |
| `cancel_previous` | Cancelar el anterior | Abortar el run **delegado** vivo (misma semántica que cancelar en la app/pipeline) y encolar el nuevo | Cancelación en el run + `tick_enqueued` |

**Vivo** = Job o `pipeline_run` de este `schedule_id` en estado no terminal (encolado / en curso). Un tick *Falló* o *Omitido* sin run no bloquea.

Queue no garantiza orden de *terminación* si hay varios workers. Cancel-previous **no** borra el plan ni el historial de ticks.

---

## Relación con M4

El flujo del worker (M4) en el paso «¿Solape?» usa `overlap_policy`. Este módulo no reimplementa misfire ni entrada de archivo.

Pausar el plan (M1) detiene **nuevos** ticks; no aplica solape a un run ya en curso (producto §10: cancelar es del job delegado).

---

## Modelo

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `overlap_policy` | Sí (default `skip`) | `skip` · `queue` · `cancel_previous` |

---

## Validación

| `error_code` (tentativo) | Cuándo |
|--------------------------|--------|
| `validation_required` | Valor desconocido |
| `schedule_forbidden` | GE/CO intenta guardar |

No hay error de negocio por elegir queue o cancel: la UI advierte el riesgo.

Al **aplicar** skip en el fire: `schedule_overlap_skip` (M4/M8), no un error de este formulario.

---

## Autorización

PA/ED: editar. GE/CO: ver. Misma matriz M1.

---

## Fuera de alcance

- Catch-up masivo de misfire (M4).
- Dependencias “tras Job A” (M6).

---

## Criterio de aceptación (diseño)

- [x] Idempotencia de ventana documentada y no configurable.  
- [x] Tres políticas; default **Omitir**.  
- [x] Guardar no cambia status; no bloquea Activar.  
- [x] Ayuda: skip ≠ mismo `scheduled_for`.  
- [x] Prototipos HTML.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) | §10 |
| [`sch_tick.md`](sch_tick.md) | Aplica la política |
| [`sch_lifecycle.md`](sch_lifecycle.md) | Pausar no aborta el run |
| [`../PLATFORM_API.md`](../PLATFORM_API.md) | §11 idempotencia |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Textos al implementar |
| [`README.md`](README.md) | Índice |
