# APP FACTORY — Operaciones de archivo (FILE_OPS)

> **Nombre mnemotécnico:** `FILE_OPS`  
> Alias: *Ops de archivo* · *Alrededor del pipeline*  
> Archivo: [`docs/APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md)  
> Padres: [`APP_FACTORY.md`](APP_FACTORY.md) · hermano: [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md)

Índice de lo que ocurre **antes, después y alrededor** de modelar → validar → transformar → emitir → conciliar.

**No** re-propone Clean, Split/Merge, Watch, Scheduler, Pipeline ni PLATFORM API. Esos productos tienen doc propio. Este archivo **apunta** a lo hecho y detalla solo el **backlog**.

---

## 0. Relación con HIGH_REUSE y la fábrica

| Documento | Rol |
|-----------|-----|
| [`APP_FACTORY.md`](APP_FACTORY.md) | Índice global (hecho vs backlog) |
| [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) | Núcleo archivo: Gate · Reverse · Match · Scout · Seed · Catalog |
| **Este doc** | Ops + orquestación: inventario §2 · huecos §4 |

```text
HIGH_REUSE
  Scout → Gate → Pipe / Reverse → Match (+ Seed, Catalog)

FILE_OPS entregado (§2)
  Clean · Split/Merge · Watch · Scheduler · Pipeline · PLATFORM API

FILE_OPS backlog (§4)
  Profiler · Repair · Archive · Schema Registry

Retirado (§3)
  File Convert · File Diff → FilePipe / File Match
```

---

## 1. Arquitectura y fronteras

```text
                 STRUCTURE SCOUT
                       ↓
                 DATA PROFILER      ← backlog
                       ↓
                   FILE CLEAN       ← hecho
                       ↓
                   FILE GATE
             ┌─────────┴─────────┐
             ↓                   ↓
         FILEPIPE          REVERSE STUDIO
             └─────────┬─────────┘
                       ↓
                  FILE MATCH
                       ↓
                 FILE ARCHIVE       ← backlog
```

Transversal **hecho:** Split ↔ Merge · Watch · Scheduler · Pipeline · PLATFORM API.  
Convert trivial → FilePipe. Diff A vs B → File Match.

| Concepto A | Concepto B | Diferencia |
|------------|------------|------------|
| **File Gate** | **File Clean** | ¿Cumple el contrato? vs arreglar / normalizar |
| **File Gate** | **File Repair** | Informe de rechazo vs correcciones **auditadas** (backlog) |
| **FilePipe** | Convert | ETL vs solo cambiar formato (no app) |
| **File Match** | File Diff | Match cubre A vs B; no hay app Diff |
| **Structure Scout** | **Data Profiler** | Estructura vs calidad de contenido (backlog) |
| **Profile Seed** | **Schema Registry** | Clone a un proyecto vs catálogo central (backlog) |
| **Historial por app** | **File Archive** | Local vs custodia E2E (backlog) |
| **Upload** | **File Watch** | Manual vs llegada automática |
| **UI / Watch / Scheduler** | **PLATFORM API** | Mismo Job; disparador HTTP |

**Intake:** Watch = dónde está el fichero; Scheduler = cuándo; apps = cómo. IFS/SFTP no se configuran dentro de Gate/Pipe/Clean. Handoff por referencia: [`FILE_PIPELINE.md`](FILE_PIPELINE.md).

---

## 2. Entregado (no es propuesta)

| Producto | App | Doc · specs |
|----------|-----|-------------|
| **File Clean** | `apps.file_clean` | [`FILE_CLEAN.md`](FILE_CLEAN.md) · [`definition_app_FILE_CLEAN/`](definition_app_FILE_CLEAN/) |
| **File Split/Merge** | `apps.file_split_merge` | [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) · [`definition_app_FILE_SPLIT_MERGE/`](definition_app_FILE_SPLIT_MERGE/) |
| **File Pipeline** | `apps.file_pipeline` | [`FILE_PIPELINE.md`](FILE_PIPELINE.md) · [`definition_app_FILE_PIPELINE/`](definition_app_FILE_PIPELINE/) |
| **File Watch** | `apps.file_watch` | [`FILE_WATCH.md`](FILE_WATCH.md) · [`definition_app_FILE_WATCH/`](definition_app_FILE_WATCH/) |
| **File Scheduler** | `apps.file_scheduler` | [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) · [`definition_app_FILE_SCHEDULER/`](definition_app_FILE_SCHEDULER/) |
| **PLATFORM API** | `apps.platform_api` | [`PLATFORM_API.md`](PLATFORM_API.md) · [`definition_app_PLATFORM_API/`](definition_app_PLATFORM_API/) |

Núcleo HIGH_REUSE (Gate, Reverse, Match, Scout, Seed): [`APP_FACTORY.md`](APP_FACTORY.md) §2.2.

---

## 3. No abrir como app

| Idea | Dónde |
|------|--------|
| **File Convert** | Modo / plantilla 1:1 en **FilePipe** |
| **File Diff** | **File Match** (clave + compare) — [`FILE_MATCH.md`](FILE_MATCH.md) |

---

## 4. Backlog

Alineado a [`APP_FACTORY.md`](APP_FACTORY.md) §3.

### 4.1 Data Profiler — revisión de aporte

Scout = estructura. Profiler = **calidad del contenido** (nulos, uniques, outliers, drift).

```text
Scout → Data Profiler → Clean → Gate → …
```

No fusionar con Scout. Validar valor diferencial **antes** de `definition_app_*` / rama.

**Producto:** [`DATA_PROFILER.md`](DATA_PROFILER.md).

### 4.2 File Repair — revisión de forma

Tras rechazo Gate: correcciones **auditadas** → archivo reparado → revalidar.

Frontera: Clean = reglas a priori; Repair = dirigido por **errores del job**. Decidir: app / modo Gate / unificar con Clean.

**Producto:** [`FILE_REPAIR.md`](FILE_REPAIR.md).

### 4.3 File Archive — previsto (forma TBD)

Custodia E2E (hashes entrada/salida, pasos Gate/Pipe, un `proceso #`). No sustituye el historial de cada app.

Forma de trabajo abierta: eventos de pipeline · API · agregador. Priorizar con pipelines en producción.

**Producto:** [`FILE_ARCHIVE.md`](FILE_ARCHIVE.md).

### 4.4 Schema Registry — previsto (forma TBD)

Catálogo central de contratos versionados (≠ Seed, ≠ Master Catalog de códigos). Hoy el contrato vive **por proyecto**.

Forma abierta: pipeline · API · catálogo UI · híbrido. No bloquea verticales ya hechos.

**Producto:** [`SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md).

---

## 5. Criterio (ítems del backlog)

Antes de rama:

1. ¿Reutiliza Company + seguridad + billing?  
2. ¿Diferenciador frente a FilePipe / Gate / Match / Scout / Clean / Pipeline?  
3. ¿App, modo de una app existente, o capa de plataforma?  
4. ¿MVP acotado?  
5. ¿Doc hijo + prototipo antes de modelos?

Al cerrar un ítem: moverlo a §2 y actualizar [`APP_FACTORY.md`](APP_FACTORY.md) §2–§3.

---

## 6. Documentos relacionados

| Documento | Relación |
|-----------|----------|
| [`APP_FACTORY.md`](APP_FACTORY.md) | Índice global |
| [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) | Familia §2 archivo |
| [`DynamicWorkspace.md`](DynamicWorkspace.md) | Chasis |
| [`ESTRUCTURA_PROYECTO.md`](ESTRUCTURA_PROYECTO.md) | Convenciones |

---

*Lo hecho no se re-propone. El backlog es solo §4.*
