# Módulo 3 — Destino (qué se ejecuta)

El plan declara **qué** Job o pipeline encolará el tick. No define el reloj (M2) ni dispara (M4).

> **Estado:** **Implementado (M3)** (`apps.file_scheduler`: destino, entrada, `save_target`)  
> **Producto:** [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) §1 · §8 · §9 · §10 entrada  
> **Índice:** [`README.md`](README.md)  
> **Previo:** programación [`sch_cron.md`](sch_cron.md)  
> **Siguiente:** tick [`sch_tick.md`](sch_tick.md)  
> **Prototipos:** [`../../prototype/file_scheduler/schedule_target.html`](../../prototype/file_scheduler/schedule_target.html) · ayuda [`schedule_target_help.html`](../../prototype/file_scheduler/schedule_target_help.html) (mismo patrón que `templates/platform_api/clients/create_help.html`)  
> **Rama:** `diseno_desarrollo_FILE_SCHEDULER`

---

## Propósito

El usuario elige el **runner** del plan: un proyecto de app con **versión publicada**, o un **pipeline** operativo. También declara **de dónde sale el archivo** (si el destino lo exige). El worker (M4) usará esa definición; este módulo solo **guarda y valida**.

```text
Plan (M1)
  → Programación (M2): cuándo
  → Destino (este módulo): qué + entrada
  → Tick (M4): a esa hora, encolar
```

**No cubre:** expresión cron, rutas IFS/SFTP (eso es Watch), solape (M5), “tras Job A” (M6), disparo real, historial de Gate/Pipe.

Scheduler dice **cuándo**. Watch (o un artifact ya en storage) dice **dónde está el fichero**. La app dice **cómo** se transforma. **File Gate no configura rutas IFS** — [`../APP_FACTORY_FILE_OPS.md`](../APP_FACTORY_FILE_OPS.md).

---

## Acción en el hub

Enlace **Destino** del rail → pantalla de este módulo (PA/ED). GE/CO: solo lectura (kind/proyecto o pipeline + origen de entrada, sin guardar).

Guardar **no** cambia `status`. Sí habilita el requisito M3 para **Activar** / **Reanudar** (junto con M2).

Editar un plan `active` actualiza el destino; el **próximo** tick usa la nueva definición. No cancela un Job ya encolado. Auditoría: `schedule.updated` (diff de destino / entrada).

---

## Modelo de destino (MVP)

Una sola definición por plan (no varios destinos).

| Campo | Obligatorio | Notas |
|-------|-------------|-------|
| `target_mode` | Sí | `job` · `pipeline` |
| `kind` | Si `job` | App a ejecutar (`file_gate`, `file_pipe`, `file_clean`, `file_match`, `reverse`, `scout`, split/merge, …). **No** `file_pipeline` aquí: use `target_mode=pipeline`. |
| `project_id` | Si `job` | Proyecto de la **misma compañía**. Debe tener **versión publicada**. |
| `published_version_number` | Si `job` | La publicada al guardar (inmutable en el run; el tick usa la publicada **vigente** al encolar — ver nota). |
| `pipeline_id` | Si `pipeline` | Pipeline de la misma compañía. `status=active` **y** versión publicada. |
| `input_origin` | Sí | `watch` · `artifact` · `none` |
| `watch_id` | Si `input_origin=watch` | Watch de la compañía. El tick resolverá el artifact (M4). Este módulo no vigila carpetas. |
| `artifact_ref` | Si `input_origin=artifact` | Hash SHA-256 del contenido en storage del tenant. El tick (M4) busca el archivo por hash e invoca el runner de la app (Clean / Gate / FilePipe) o el pipeline. |
| `pipeline_inputs_resolved` | Si `pipeline` + `none` | Confirmación explícita: la cadena no exige upload en el tick (entradas ya resueltas en pasos). |

**Versión al tick:** el fire usa la versión **publicada vigente** del proyecto/pipeline en el instante de encolar (paridad UI/API). Si entre el guardado y el tick se despublica → `schedule_no_published_target` (M4/M8), no un archivo vacío.

Persistencia: el plan **apunta**; no copia parsers ni pasos del pipeline.

---

## Job vs pipeline

| `target_mode` | Qué se encola | Historial |
|---------------|---------------|-----------|
| `job` | Un `run_*_job` (`kind` + proyecto + versión publicada) | Historial de **esa app** |
| `pipeline` | Orquestador (`pipeline_id`); no se reimplementa la cadena | Tablero / `pipeline_run_id` (Pipeline §7.1) |

El tick **no** bypasea tenancy. El sistema debe poder ejecutar **cada** proyecto del destino (job: ese proyecto; pipeline: **todos** los pasos). Si falta permiso en uno → se deniega el fire completo (producto §9). Validar al guardar si es posible; el worker revalida al encolar.

---

## Entrada de archivo (producto §10)

Un cron sobre Gate/Pipe/Clean (u otra app de archivo) **sin** archivo no es ejecutable. No inventar un fichero vacío.

| `input_origin` | Significado | Típico |
|----------------|-------------|--------|
| `watch` | File Watch ya tiene (o tendrá) el lote; el Scheduler dispara o reintenta a la hora | Cierre nocturno sobre bandeja vigilada |
| `artifact` | Referencia ya en storage (`artifact_ref`) | Reproceso de un hash conocido |
| `none` | El destino **no** exige upload en el tick | Solo pipelines con entradas resueltas. **Prohibido** si `target_mode=job` sobre app de archivo |

Si falta entrada cuando el destino la exige → no guardar (este módulo) o no encolar (`schedule_missing_input` en M4).

**Fuera de este módulo:** configurar SFTP, carpeta IFS, patrón de nombre — viven en Watch.

---

## Validación

| `error_code` (tentativo) | Cuándo |
|--------------------------|--------|
| `validation_required` | Falta modo, proyecto, pipeline, Watch o `artifact_ref` |
| `schedule_no_published_target` | Proyecto o pipeline sin versión publicada; pipeline no `active` |
| `schedule_missing_input` | Job de archivo con `input_origin=none`, o Watch/artifact vacío cuando aplica |
| `schedule_forbidden` | GE/CO intenta guardar; o el actor no puede ejecutar el/los proyecto(s) destino |
| `schedule_target_cross_tenant` | Proyecto/pipeline/Watch de otra compañía (404 opaco al acceso directo) |

Servicio: `ok` / `error_code` / `user_message`. Errores **inline** + no guardar. Prototipo: alerta al enviar y mensaje bajo el campo.

---

## Autorización

PA/ED: editar. GE/CO: ver. Misma matriz M1. Producto §9: destinos ejecutables por el contexto de compañía.

---

## Relación con el tick

| Este módulo | M4 Tick |
|-------------|---------|
| Guarda `target_mode` + ids + entrada | Encola Job o `pipeline_run` |
| Exige versión publicada al guardar | Revalida al fire; `schedule_no_published_target` si desapareció |
| Declara origen de archivo | Resuelve artifact; si no hay → `schedule_missing_input` |
| No habla de cron | Usa `scheduled_for` de M2 |

`trigger_source=scheduler`. El run delegado lleva `schedule_id`.

---

## Auditoría

`schedule.updated` con snapshot `target_mode`, `kind`, `project_id` / `pipeline_id`, `input_origin`, `watch_id` / `artifact_ref` (metadatos; no PII de celdas ni bytes del archivo).

---

## Fuera de alcance

- Worker Railway, cola, misfire.  
- Calendario (M2).  
- Dependencias “tras A” (M6).  
- Código Django.  
- UI de Watch / diseñador de pipeline.

---

## Criterio de aceptación (diseño)

- [ ] `target_mode` job (kind + proyecto publicado) o pipeline (`pipeline_id` activo + publicado).  
- [ ] `input_origin` watch / artifact / none con las reglas de este documento.  
- [ ] Sin campo de ruta IFS.  
- [ ] Validación `schedule_no_published_target` / `schedule_missing_input`; bloquea guardar.  
- [ ] No cambia status al guardar.  
- [x] Prototipos HTML (Simple Browser: `/prototype/file_scheduler/schedule_target.html`).  
- [x] Ayuda: propósito, campos, job vs pipeline, entrada, acciones.

---

## Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`../FILE_SCHEDULER.md`](../FILE_SCHEDULER.md) | §1 · §8 · §9 · §10 entrada |
| [`sch_lifecycle.md`](sch_lifecycle.md) | Hub; Activar exige M2+M3 |
| [`sch_cron.md`](sch_cron.md) | Reloj |
| [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) | Destino `pipeline_id`; versión publicada |
| [`../FILE_WATCH.md`](../FILE_WATCH.md) | Origen `watch` |
| [`../APP_FACTORY_FILE_OPS.md`](../APP_FACTORY_FILE_OPS.md) | `artifact_ref`; no IFS en Gate |
| [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md) | Textos al implementar |
| [`README.md`](README.md) | Índice |
