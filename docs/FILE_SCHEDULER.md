# FILE SCHEDULER — Ejecución programada y dependencias

> **Nombre mnemotécnico:** `FILE_SCHEDULER`  
> Alias: *Programador de jobs* · *Cron de archivos*  
> Archivo: [`docs/FILE_SCHEDULER.md`](FILE_SCHEDULER.md)  
> Estado: **previsto (se desarrollará)** — **pendiente definir forma de trabajo**  
> Familia: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §11 · prioridad ⭐⭐⭐ (plataforma; con Watch)  
> Tipo: **capa de plataforma**  
> Pareja: [`FILE_WATCH.md`](FILE_WATCH.md) · hermano: [`PLATFORM_API.md`](PLATFORM_API.md) · roadmap DMS Fase 3

---

## 1. Resumen ejecutivo

**File Scheduler** dispara Jobs por **tiempo** (cron / calendario) o por **dependencia** (“cuando termine el Job A”).

```text
Scheduler (cron / “tras A”) ─┐
Watch / UI / API            ─┼→ Job (app + versión publicada) → notificar
```

No requiere un `project_kind` por formato de archivo: orquesta runners ya existentes (`DmsExecutionJob` / jobs de verticales).

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Problema** | Cierres, consolidaciones y re-procesos se lanzan a mano o se olvidan |
| **Solución** | Calendarios + cadenas de jobs con el mismo runner auditable |
| **Beneficio** | Operación predecible; menos dependencia de un operador en pantalla |
| **Audiencia** | Ops, integración, finanzas |

---

## 2. Función

| Hace | No hace |
|------|---------|
| Cron (diario 02:00, fin de mes, lunes…) | Esperar a que “aparezca” un archivo (Watch) |
| “Tras Job A → Job B” | Reimplementar parsers / reglas de cada app |
| Reintentos programados de fallidos | Sustituir el historial de cada vertical |

**Disparador:** **reloj** o **cadena de jobs**.

---

## 3. Forma de trabajo (pendiente de decisión)

Se desarrollará; elegir **una o varias**:

| Forma | Descripción |
|-------|-------------|
| **Dentro de un pipeline** | Nodo schedule / dependencia — [`FILE_PIPELINE.md`](FILE_PIPELINE.md) |
| **Por pedido de API** | Crear/actualizar schedules vía PLATFORM_API o admin API |
| **Monitor / worker** | Proceso que evalúa cron y encola Jobs |
| **Otras** | Calendarios por compañía, ventanas de mantenimiento, “solo días hábiles” |
| **Todas las anteriores** | Motor de schedules + adaptadores (UI, API, pipeline) |

Alinear con Watch para un modelo único **disparador → Job**.

---

## 4. Frontera con Watch

| **Watch** | **Scheduler** |
|-----------|---------------|
| ¿Llegó el archivo? | ¿Es la hora / terminó el paso anterior? |
| Drop impredecible | Cierre mensual, Match nocturno, reintento 06:00 |

---

## 5. Ejemplos

1. **Consolidación mensual** — día 1 03:00: Merge de extractos del mes → Match vs ERP → informe.  
2. **Dependencia** — “Tras Gate ACCEPTED de ventas → FilePipe v5” sin pulsar Ejecutar.  
3. **Con Watch** — Watch ingesta el archivo; Scheduler reintenta fallidos o dispara Match de cierres.  
4. **Clean nocturno** — 02:00 Clean de bandeja acumulada → Gate.

---

## 6. Criterio antes de implementar

1. ¿Forma de trabajo (§3) acordada con Watch/API?  
2. ¿Cola / workers disponibles en Railway?  
3. ¿Permisos: quién crea schedules (PA plataforma vs PA proyecto)?  
4. ¿Idempotencia si el cron se solapa con un Job largo?

---

## 7. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Paraguas §11 |
| [`FILE_PIPELINE.md`](FILE_PIPELINE.md) | Orquestación; Scheduler dispara `pipeline_id` |
| [`FILE_WATCH.md`](FILE_WATCH.md) | Disparo por llegada |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Disparo HTTP |

---

*Documento vivo. Desarrollo previsto; forma de trabajo abierta.*
