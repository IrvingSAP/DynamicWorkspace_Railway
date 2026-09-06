# FILE WATCH — Recepción automática de archivos

> **Nombre mnemotécnico:** `FILE_WATCH`  
> Alias: *Bandeja vigilada* · *Ingestión por llegada*  
> Archivo: [`docs/FILE_WATCH.md`](FILE_WATCH.md)  
> Estado: **implementado M1–M10** (MVP en `apps.file_watch`) · bridge tick ↔ lote vía `claim_pending_batch`  
> Familia: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §10 · prioridad ⭐⭐⭐⭐⭐ (plataforma)  
> Tipo: **capa de plataforma** (no app de menú con wizard de campos)  
> Pareja: [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) · disparador hermano: [`PLATFORM_API.md`](PLATFORM_API.md)  
> **Contexto 2026-09:** App Django M1–M10 operativa. El plan con `input_origin=watch` hace claim del lote pending; sin lote → `schedule_missing_input`. Worker: `process_watch_intake`.

---

## 1. Resumen ejecutivo

**File Watch** detecta que **llegó un archivo** y lo deja disponible en storage del tenant (y/o dispara el mismo Job que hoy se ejecuta a mano en la UI: Clean, Gate, Pipe, Match, Split/Merge, …).

```text
Watch (llegó un archivo)  ─┐
Scheduler / UI / API      ─┼→ Job (app + versión publicada) → notificar
```

Orígenes posibles: carpeta, SFTP, API/webhook, cloud storage, correo.

### Propuesta de valor

| Aspecto | Descripción |
|---------|-------------|
| **Problema** | Todo el pipeline depende de que un UF haga upload → ejecutar |
| **Solución** | Ingestión automática al detectar llegada + reglas de enrutado a proyecto/versión |
| **Beneficio** | Operación 24×7, menos error humano, mismo runner auditable |
| **Audiencia** | Ops, integración, tesorería / nómina |

---

## 2. Función

| Hace | No hace |
|------|---------|
| Vigilar un origen y detectar llegada | Definir reglas de negocio de cada app |
| Emparejar archivo → proyecto + versión publicada (o dejar lote para el Scheduler) | Sustituir el historial de cada vertical |
| Idempotencia, reintentos, cuotas | Ser “otra app” de perfil/campos |
| Notificar (p. ej. Resend) | Reemplazar PLATFORM_API (son disparadores hermanos) |
| Entregar **lotes nuevos** (hashes distintos por llegada) | Fijar un hash único en el plan (eso es origen **Artifact** del Scheduler) |

**Disparador:** evento de **llegada** de archivo.

---

## 3. Forma de trabajo (**decisión M2**)

**Decisión:** modelo unificado **bandeja + adaptador de origen** (`source_kind`). Una bandeja, un origen activo; el catálogo de adaptadores crece sin otra app.

Detalle: [`definition_app_FILE_WATCH/wach_source.md`](definition_app_FILE_WATCH/wach_source.md).

| Forma | Estado |
|-------|--------|
| **Monitor a la espera** | **MVP** — SFTP + carpeta gestionada del tenant |
| **Por pedido de API** | **MVP** — adaptador `api_push` (registra llegada en la bandeja; no sustituye el disparo HTTP de Jobs de PLATFORM_API) |
| **Dentro de un pipeline** | Pipeline es **destino** (M4 `pipeline_id`), no el origen de la bandeja. Paso “Watch” en el diseñador = fuera de MVP |
| **Correo / cola / cloud** | Fuera de MVP; `source_kind` extensible |
| **Todas las anteriores** | Misma entidad Watch + adaptadores — sí como modelo, no como “todo implementado día 1” |

Documentar en FILE_OPS §18 cuando se implemente.

---

## 4. Frontera con Scheduler (estado actual)

| **Watch** (futuro) | **Scheduler** (implementado) |
|--------------------|------------------------------|
| Dispara por **llegada** de archivo | Dispara por **tiempo** o dependencia entre jobs |
| Drop impredecible del banco a las 14:37 | Cron diario 02:00 o “tras Job A” |
| El plan guarda un `watch_id` (bandeja) | Origen **Artifact**: el plan guarda un `artifact_ref` (hash fijo → reproceso) |
| Cada llegada = contenido **nuevo** (otro hash) | Cada tick con Artifact = **mismo** contenido |

### Dos modos de combinación (producto)

1. **Watch dispara al llegar** — el Job corre en el momento del drop (sin esperar cron).  
2. **Watch ingesta + Scheduler a la hora** — Watch deja el lote en storage; el plan con `input_origin=watch` a las 02:00 pregunta “¿hay lote pendiente en este `watch_id`?” y ejecuta el runner.

Hoy el Scheduler ya tiene UI/campo `watch_id`, pero el worker de ticks **no** resuelve el lote: falla con `schedule_missing_input` hasta que exista File Watch + el puente en M4 ([`definition_app_FILE_SCHEDULER/sch_tick.md`](definition_app_FILE_SCHEDULER/sch_tick.md)).

**Orden de implementación:** Scheduler ya está en curso; Watch sigue **después** (o en paralelo solo tras cerrar §3).

---

## 5. Artifact vs Watch (no confundir)

| Origen en el plan | Qué identifica | Uso |
|-------------------|----------------|-----|
| `input_origin=artifact` | Hash SHA-256 fijo en el plan | Reproceso / reintento / QA del **mismo** archivo |
| `input_origin=watch` | Código de bandeja (`watch_id`) | Archivos **nuevos** que llegan a esa bandeja |

Watch **no** hereda la limitante de Artifact: no se casa con un único hash en la configuración del plan. Las reglas de “cuál lote tomar” (último, no procesados, uno vs varios) se definen en Watch, no en el cron.

---

## 6. Ejemplos

1. **Extracto bancario** — SFTP `extracto_YYYYMMDD.csv` → Gate (versión publicada) → Pipe → notificar tesorería.  
2. **Nómina proveedor** — ZIP en carpeta vigilada → Split por sucursal → Gate por parte → correo si hay rechazos.  
3. **Combinado** — Watch recibe el archivo del día; Scheduler a las 06:00 reintenta fallidos o dispara Match de cierres.  
4. **Vs hoy (Scheduler solo)** — con Artifact el tick ya invoca runners de Clean / Gate / File Pipe leyendo el hash en storage; eso cubre **reproceso**, no ingestión diaria. Watch es lo que falta para “archivo nuevo cada día”.

Watch **no** se implementa como pantalla de rutas dentro de File Gate / Pipe. Lee el origen, deja el archivo en intake/storage y llama al runner (o deja el lote para el Scheduler).

**Runners:** el Scheduler ya resuelve Artifact → upload interno → `run_clean_job` / `validate_and_run` / `run_full_job` (y pipeline con artifact). Watch deberá alimentar el **mismo** contrato (archivo en storage + mismo runner), no un ETL paralelo.

---

## 7. Coste / riesgos

Alto en **ops y seguridad**: credenciales, cuotas, duplicados (mismo archivo dos veces), reintentos, notificaciones. No es solo UI.

---

## 8. Criterio antes de implementar

1. ¿Forma de trabajo elegida (tabla §3)? — **Sí en diseño** ([`definition_app_FILE_WATCH/wach_source.md`](definition_app_FILE_WATCH/wach_source.md)); falta OK de implementación.  
2. ¿Modelo de Job / Pipeline encadenable estable? — [`FILE_PIPELINE.md`](FILE_PIPELINE.md)  
3. ¿Idempotencia y tenancy claros?  
4. ¿Relación explícita con PLATFORM_API y Pipeline (`pipeline_id`)?  
5. ¿Contrato del lote pendiente hacia el tick del Scheduler (`watch_id` → artifact resuelto) alineado con [`definition_app_FILE_SCHEDULER/sch_target.md`](definition_app_FILE_SCHEDULER/sch_target.md) · [`sch_tick.md`](definition_app_FILE_SCHEDULER/sch_tick.md)?  
6. ¿Reglas de “lote vacío” vs `schedule_missing_input` documentadas?

---

## 9. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`definition_app_FILE_WATCH/`](definition_app_FILE_WATCH/) | Specs por módulo (análisis y diseño); índice [`README.md`](definition_app_FILE_WATCH/README.md) |
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Paraguas §10 |
| [`FILE_PIPELINE.md`](FILE_PIPELINE.md) | Orquestación; Watch dispara `pipeline_id` |
| [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) | Disparo por tiempo / dependencia; §4 frontera Watch; §10 entrada |
| [`definition_app_FILE_SCHEDULER/`](definition_app_FILE_SCHEDULER/) | Specs del plan: destino Watch/Artifact, tick, errores |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Disparo HTTP del mismo Job / Pipeline |

---

*Documento vivo. Watch pendiente; Scheduler ya en producto — alinear frontera Artifact vs Watch y el puente `watch_id` → tick.*
