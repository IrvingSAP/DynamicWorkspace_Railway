# FILE SCHEDULER — Ejecución programada y dependencias

> **Nombre mnemotécnico:** `FILE_SCHEDULER`  
> Alias: *Programador de jobs* · *Cron de archivos*  
> Archivo: [`docs/FILE_SCHEDULER.md`](FILE_SCHEDULER.md)  
> Estado: **MVP hecho** (M1–M10 en `apps.file_scheduler`) · worker `process_schedule_ticks` · forma MVP = UI + worker cron (Job o `pipeline_id`)  
> Familia: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §11 · prioridad ⭐⭐⭐ (plataforma; con Watch)  
> Tipo: **capa de plataforma**  
> Pareja: [`FILE_WATCH.md`](FILE_WATCH.md) · hermano: [`PLATFORM_API.md`](PLATFORM_API.md) · roadmap DMS Fase 3  
> **Auditoría / errores:** hereda contrato de [`FILE_PIPELINE.md`](FILE_PIPELINE.md) **§6 · §7 · §7.1** y [`PLATFORM_API.md`](PLATFORM_API.md) **§9 · §10.2 · §11** — este doc añade lo **propio del schedule** (CRUD + tick); no duplica pasos ni filas de app.  
> **Specs por módulo:** [`definition_app_FILE_SCHEDULER/`](definition_app_FILE_SCHEDULER/)

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

El Scheduler **no reescribe** parsers, informe por paso ni historial de cada vertical. Delega en el Job o en un `pipeline_id` y **enlaza** `job_id` / `pipeline_run_id`.

---

## 2. Función

| Hace | No hace |
|------|---------|
| Cron (diario 02:00, fin de mes, lunes…) | Esperar a que “aparezca” un archivo (Watch) |
| “Tras Job A → Job B” | Reimplementar parsers / reglas de cada app |
| Reintentos programados de fallidos | Sustituir el historial de cada vertical ni el §7.1 del Pipeline |
| Auditar CRUD del schedule y cada tick | Auditar diseño de esquemas o editor de pipeline (eso sigue en cada app / Pipeline) |

**Disparador:** **reloj** o **cadena de jobs**.

---

## 3. Forma de trabajo (MVP cerrado; extensiones Fase 2)

**MVP:** UI de planes + **worker cron** que evalúa ticks y encola el mismo Job/Pipeline que la UI. Destino: proyecto publicado o `pipeline_id`. Entrada: artifact o `watch_id` (lote Watch).

| Forma | Estado |
|-------|--------|
| **Monitor / worker** | **MVP** — `process_schedule_ticks` |
| **Dentro de un pipeline** | Pipeline es **destino** (`pipeline_id`); nodo schedule en el diseñador = Fase 2 |
| **Por pedido de API** | Disparo de Job/Pipeline vía PLATFORM API; CRUD HTTP de schedules = Fase 2 |
| **Otras** | Ventanas / días hábiles parciales según M2; ampliar calendarios = Fase 2 |

Alineado con Watch: modelo único **disparador → Job**. Las secciones §7–§10 valen para worker cron **y** para un futuro nodo en pipeline.

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
3. ¿Permisos: quién crea schedules — **cerrado:** US de la compañía con rol PA o ED (§9)?  
4. ¿Idempotencia si el cron se solapa con un Job largo — §10?  
5. ¿Auditoría §7 (CRUD + tick) y errores §8 con `error_code` / `user_message`?  
6. ¿Entrada de archivo para destinos que la exigen (Watch, artifact, o solo pipelines sin upload) — §10?

Servicios Django: retorno `ok` / `error_code` / `user_message` — [`definition_app/UI_MESSAGES.md`](definition_app/UI_MESSAGES.md).

---

## 7. Auditoría (obligatorio en el diseño)

Mismo criterio que Pipeline §7.1 y API §10.2: **no hay ejecución anónima**; eventos **append-only**; sin PII de celdas (solo metadatos y hashes).

El Scheduler cubre **dos planos**. El detalle de **pasos** de un pipeline y el historial fino de cada app **no se copian aquí**: se enlazan.

```text
FILE_SCHEDULER
  A) CRUD de la definición del schedule
  B) Tick / disparo (trigger_source = scheduler | dependency)
       ↓ delega
  Job de app  o  Pipeline run  →  Pipeline §7–§7.1 / historial de la app / API §10.2
```

### A) Definición (CRUD del schedule)

Paridad con Pipeline §7.1-A, aplicada al **plan**, no al pipeline:

| Evento | Qué registrar |
|--------|----------------|
| Creación | `created_by` (user), `created_at`, `company_id` |
| Edición | `updated_by`, `updated_at`, snapshot o diff (cron/ventana, destino `kind`+proyecto o `pipeline_id`, política de solape) |
| Pausar / reanudar | actor + timestamp + valor anterior/nuevo |
| Archivar / baja lógica | actor + timestamp |

El tick usa la **definición activa** del schedule (no un borrador a medias). El CRUD se audita en **UI / admin de Scheduler**. PLATFORM API MVP **no** audita el diseño de schedules (API §10.2: CRUD fuera de API).

### B) Disparo (proceso / tick)

Paridad con Pipeline §7.1-B y API §10.2. Actor típico: `system:scheduler`.

| Campo | Uso |
|-------|-----|
| `trigger_source` | `scheduler` o `dependency` (valores ya listados en Pipeline §7.1) |
| `schedule_id` | Identidad del plan |
| cron / ventana | Evidencia de *por qué* se disparó ahora |
| `triggered_by` | `system:scheduler` |
| `triggered_at` · `started_at` · `finished_at` · `duration_ms` | Timing del tick y del job/run delegado |
| `company_id` | Tenancy |
| `correlation_id` | Traza Scheduler → orquestador → jobs de app |
| Clave de ventana / `idempotency_key` | Un slot (`schedule_id` + `scheduled_for`) = un fire |
| `job_id` / `pipeline_run_id` | Mismo id que UI y `GET` API |
| `dry_run` | Si aplica (p. ej. “próxima ejecución” sin efectos) |
| `attempt` / `retry_of_run_id` | Reintentos: **nuevo** run (API §10.1; Pipeline §7.1-D) |

El run delegado (pipeline o job suelto) debe persistir `trigger_source=scheduler` (o `dependency`), `schedule_id` y cron/ventana — ejemplo ya en Pipeline §7.1-F.

### Eventos sugeridos (timeline)

```text
schedule.created
schedule.updated
schedule.paused | resumed | archived
schedule.tick_skipped     (p. ej. overlap, pausado)
schedule.tick_enqueued
schedule.tick_failed      (fallo del Scheduler antes o al encolar)
schedule.notify_sent      (opcional)
```

Borrado de evidencia = soft + política PA, igual que UI/API.

---

## 8. Errores de ejecución

Capas como PLATFORM API §9. El Scheduler **no inventa** códigos de fila/campo ni de paso de pipeline.

| Capa | Ejemplos Scheduler | Qué hacer |
|------|--------------------|-----------|
| Auth / tenant | Compañía inactiva; schedule de otra company | Rechazar (403 / 404 opaco) |
| Validación / negocio del plan | Cron inválido; destino sin versión publicada; pipeline no `active`; schedule pausado | Rechazar **antes** de encolar |
| Infra Scheduler | Worker caído; cola Railway; timeout al encolar; solape | Códigos `schedule_*`; auditar `tick_failed` o `tick_skipped` |
| Ejecución delegada | Rechazo Gate, filas Pipe, paso pipeline `failed` | **Enlazar** el job/run; `error_code` / `user_message` de la app o Pipeline §7 |

Códigos propios (catálogo UI al implementar):

| `error_code` | Significado |
|--------------|-------------|
| `schedule_paused` | El plan no está `active` (incluye `inactive`, `in_progress`, `archived`) |
| `schedule_overlap_skip` | Slot omitido porque el run anterior sigue vivo (si esa es la política) |
| `schedule_no_published_target` | Destino sin versión publicada o pipeline no operativo |
| `schedule_misfire` | Ventana perdida (worker tarde / caído) |
| `schedule_enqueue_failed` | No se pudo encolar el Job/run |
| `schedule_artifact_not_found` | Hash de artifact sin archivo en storage del tenant |
| `schedule_runner_unsupported` | Kind de destino aún no cableado al runner (Match, Split, …) |
| `schedule_missing_input` | Destino de archivo sin artifact ni Watch |

Informe OK/ERROR por **paso** de pipeline: no copiar; abrir el `pipeline_run_id`. Jobs sueltos: historial de esa app.

---

## 9. Autorización

Hereda [`FILE_PIPELINE.md`](FILE_PIPELINE.md) §6. No inventar roles nuevos.

| Regla | Detalle |
|-------|---------|
| Tenant | El schedule pertenece a una `Company`; sin lectura cruzada |
| **Crear** plan | Usuario tipo **`US`** (`UserProfile.user_type`) de **esa** `Company`, con rol de membresía **PA** o **ED**. **UF no crea** planes. GE/CO (aunque sean US) no crean. |
| Configurar (editar, pausar, cron, destino) | PA/ED **del plan** (matriz Pipeline “Watch / Scheduler enlazado”). El creador US queda PA. Pueden invitarse UF como miembros; no por ello pueden dar de alta un plan nuevo. |
| Ejecutar tick | Identidad de **sistema** en nombre de la compañía; **no** bypasea tenancy |
| Destinos | Debe poder ejecutarse **cada** proyecto (o cada paso del pipeline); si no, se deniega el fire completo |
| Versión publicada | Igual que UI/API: solo definición publicada del destino |

El run queda con `trigger_source=scheduler` (o `dependency`). Ver también [`docs/security/SEGURIDAD_Y_ACCESOS.md`](security/SEGURIDAD_Y_ACCESOS.md).

---

## 10. Operación: solape, idempotencia, entrada, reintento, cancelación, tablero

### Solape

Si un tick llega y el Job/run anterior del mismo schedule **sigue vivo**, la política MVP debe ser una (documentar la elegida al implementar):

| Política | Efecto | Auditoría |
|----------|--------|-----------|
| **Skip** (recomendado MVP) | No encolar; `tick_skipped` | `schedule_overlap_skip` |
| Queue | Encolar detrás | — |
| Cancel-previous | Abortar el run anterior y disparar el nuevo | Cancelación auditada en el run delegado |

### Idempotencia de ventana

Análogo a `Idempotency-Key` (API §11): el mismo `schedule_id` + `scheduled_for` no debe crear dos fires. Reintento humano o de política = **nuevo** run con `retry_of_run_id` y clave de ventana distinta o explícita.

### Entrada de archivo

Un cron sobre Gate/Pipe/Clean **sin** archivo no es ejecutable. El schedule debe declarar origen:

- File Watch (llegó el lote; el Scheduler reintenta o dispara el cierre), o  
- Artifact / referencia ya en storage, o  
- Solo destinos que **no** exigen upload (p. ej. algunos pipelines con entradas resueltas).

Si falta entrada → `schedule_missing_input`; no inventar un archivo vacío.

**Mejora futura (runners, no IFS en cada app):** Watch/Scheduler/Pipeline no sustituyen el upload de Ejecutar; lo **alimentan**. Los `run_*_job` de Gate, Pipe, Clean, Match, etc. deberán aceptar `artifact_ref` (hash / objeto en storage), no solo `<input type="file">`. Paridad con el handoff de Pipeline. **File Gate no configura rutas IFS** — eso es Watch (y un futuro drop). Detalle: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) (orquestación · `artifact_ref`).

### Reintento y cancelación

- Reintento = nuevo run (no reescribir el fallido).  
- Cancelar aborta el job/run **delegado** (misma semántica que UI/API); **no** borra el schedule.  
- Registrar `cancelled_by` / `cancelled_at` en el run delegado (Pipeline §7.1-D).

### Notificaciones

Si hay correo/webhook al fallar el tick o el run: destinatario, resultado, timestamp (Pipeline §7.1-D). No loguear contenido de archivo.

### Tablero

Runs con `trigger_source=scheduler` **alimentan** el tablero de Pipeline (paridad API §10.3). Jobs sueltos (sin pipeline) van al **historial de esa app**, no al tablero de pipelines salvo producto futuro unificado. Dry-run fuera del pulso.

---

## 11. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Paraguas §11 |
| [`definition_app_FILE_SCHEDULER/`](definition_app_FILE_SCHEDULER/) | Specs por módulo (fase de diseño) |
| [`FILE_PIPELINE.md`](FILE_PIPELINE.md) | Orquestación; dispara `pipeline_id`; **§6 · §7 · §7.1** (heredar; no duplicar pasos) |
| [`FILE_WATCH.md`](FILE_WATCH.md) | Disparo por llegada |
| [`PLATFORM_API.md`](PLATFORM_API.md) | Disparo HTTP; **§9 · §10.2 · §11** (capas de error, auditoría de máquina, idempotencia) |
| [`definition_app/UI_MESSAGES.md`](definition_app/UI_MESSAGES.md) | `error_code` / `user_message` (incl. `schedule_*` al implementar) |
| [`docs/security/SEGURIDAD_Y_ACCESOS.md`](security/SEGURIDAD_Y_ACCESOS.md) | Tenant y roles |

---

*Documento vivo. M1–M10 en código (`apps.file_scheduler`). Forma de trabajo (§3) abierta.*
