# APP FACTORY — Índice de verticales y backlog

> **Nombre mnemotécnico:** `APP_FACTORY`  
> Alias: *Fábrica de aplicativos* · *Índice de verticales*  
> Archivo: [`docs/APP_FACTORY.md`](APP_FACTORY.md)

Paraguas del **chasis** DynamicWorkspace + FilePipe (DMS): qué ya está en `main`, qué sigue abierto y cómo aceptar un vertical nuevo.

**No** es un listado de “ideas por construir”. Lo entregado vive en su doc de producto y en `apps.*`. Este archivo **apunta**; no duplica specs.

---

## 0. Relación entre documentos

| Documento | Rol |
|-----------|-----|
| [`DynamicWorkspace.md`](DynamicWorkspace.md) | Chasis: tenant, workspace, mapa de apps Django |
| [`DataMappingStudio.md`](DataMappingStudio.md) · [`definition_app_DMS/`](definition_app_DMS/) | Motor FilePipe / ETL |
| [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) | Familia archivo §2 (Gate · Reverse · Match · Scout · Seed · **Catalog**) |
| [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | Ops: inventario hecho §2 · backlog Profiler · Repair · Archive · Registry §4 |
| [`ESTRUCTURA_PROYECTO.md`](ESTRUCTURA_PROYECTO.md) | Carpetas y convenciones al abrir un vertical |

```text
APP_FACTORY.md          ← este índice (hecho vs backlog)
        ├── HIGH_REUSE  ← núcleo archivo (Catalog = único §2 abierto)
        └── FILE_OPS    ← ops: hecho §2 · backlog §4
```

---

## 1. Idea central (sigue vigente)

La plataforma es un **chasis multi-tenant**, no una sola app. Discriminador: `Project.project_kind`.

| Capacidad compartida | Dónde vive |
|----------------------|------------|
| Tenant | `Company` |
| Usuarios y perfiles | `UserProfile` |
| Billing / suscripción | `billing` |
| Seguridad (login, correo, 2FA, Resend) | `security` + `core` |
| Roles por proyecto | `PA` / `ED` / `CO` / `GE` (+ `CG` donde aplique) |
| Membresías y auditoría | `projects` + historial de cada vertical |
| Deploy | Railway + PostgreSQL + Resend |

Dos motores:

1. **Esquema dinámico** — `FieldDefinition` + `Record` + `FieldValue` → `workspace`.
2. **Transformación de archivos** — parse → mapear → reglas → serializar → `dms` y skins (`file_gate`, `reverse`, …).

```
Company + Seguridad + Billing + Roles + Auditoría
        │
   Project (project_kind)
   ├── workspace     → hojas / registros
   ├── dms           → FilePipe
   └── <kind>        → vertical (reusa chasis ± motores)
```

Capas **sin** `project_kind` de archivo: Watch, Scheduler, PLATFORM API (y Pipeline como contenedor de orquestación).

---

## 2. Entregado (no es propuesta)

Inventario compacto. Detalle y Fase 2 de cada uno: doc hijo.

### 2.1 Workspace y FilePipe

| Producto | Código | Doc |
|----------|--------|-----|
| Chasis / workspace | `apps.company` · `accounts` · `projects` · `fields` · `records` · … | [`DynamicWorkspace.md`](DynamicWorkspace.md) |
| FilePipe (DMS) | `apps.dms` | [`DataMappingStudio.md`](DataMappingStudio.md) · [`definition_app_DMS/`](definition_app_DMS/) |

### 2.2 Familia archivo (reutilización alta)

Paraguas: [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md).

| Producto | App | Doc · specs |
|----------|-----|-------------|
| **FILE GATE** | `apps.file_gate` | [`FILE_GATE.md`](FILE_GATE.md) · [`definition_app_FILE_GATE/`](definition_app_FILE_GATE/) |
| **Reverse Studio** | `apps.reverse_studio` | [`REVERSE_STUDIO.md`](REVERSE_STUDIO.md) |
| **File Match** | `apps.file_match` | [`FILE_MATCH.md`](FILE_MATCH.md) |
| **Structure Scout** | `apps.structure_scout` | [`STRUCTURE_SCOUT.md`](STRUCTURE_SCOUT.md) · [`definition_app_STRUCTURE_SCOUT/`](definition_app_STRUCTURE_SCOUT/) |
| **Profile Seed** | `apps.profile_seed` | [`PROFILE_SEED.md`](PROFILE_SEED.md) · [`definition_app_PROFILE_SEED/`](definition_app_PROFILE_SEED/) |

### 2.3 FILE_OPS y plataforma

Paraguas: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md).

| Producto | App / capa | Doc · specs |
|----------|------------|-------------|
| **File Clean** | `apps.file_clean` | [`FILE_CLEAN.md`](FILE_CLEAN.md) · [`definition_app_FILE_CLEAN/`](definition_app_FILE_CLEAN/) |
| **File Split/Merge** | `apps.file_split_merge` | [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) · [`definition_app_FILE_SPLIT_MERGE/`](definition_app_FILE_SPLIT_MERGE/) |
| **File Pipeline** | `apps.file_pipeline` | [`FILE_PIPELINE.md`](FILE_PIPELINE.md) · [`definition_app_FILE_PIPELINE/`](definition_app_FILE_PIPELINE/) |
| **File Watch** | `apps.file_watch` | [`FILE_WATCH.md`](FILE_WATCH.md) · [`definition_app_FILE_WATCH/`](definition_app_FILE_WATCH/) |
| **File Scheduler** | `apps.file_scheduler` | [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) · [`definition_app_FILE_SCHEDULER/`](definition_app_FILE_SCHEDULER/) |
| **PLATFORM API** | `apps.platform_api` | [`PLATFORM_API.md`](PLATFORM_API.md) · [`definition_app_PLATFORM_API/`](definition_app_PLATFORM_API/) |

**Cubierto / no abrir app:**

| Idea retirada | Dónde vive |
|---------------|------------|
| File Convert | Modo simple en FilePipe |
| File Diff | [`FILE_MATCH.md`](FILE_MATCH.md) |
| Scheduling DMS / bandeja vigilada | File Scheduler · File Watch |

---

## 3. Backlog (sí es propuesta o revisión)

Orden sugerido. Nada de esta lista está entregado como vertical cerrado.

| Orden | Ítem | Tipo | Doc |
|-------|------|------|-----|
| **1** | **Master Catalog** (maestros / lookups) | Vertical §2 | [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) §5 — extraer `MASTER_CATALOG.md` al priorizar |
| **2** | **Data Profiler** | Revisión de aporte (¿app?) | [`DATA_PROFILER.md`](DATA_PROFILER.md) · FILE_OPS §4.1 |
| **3** | **File Repair** | Revisión (app / modo Gate / Clean) | [`FILE_REPAIR.md`](FILE_REPAIR.md) · FILE_OPS §4.2 |
| **4** | **File Archive** | Plataforma; forma TBD | [`FILE_ARCHIVE.md`](FILE_ARCHIVE.md) · FILE_OPS §4.3 |
| **5** | **Schema Registry** | Plataforma; forma TBD | [`SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md) · FILE_OPS §4.4 |
| **6** | **Formularios / captura no-code** | Reutilización media (workspace) | — (sin `definition_app_*`) |
| — | Checklists / inspecciones | Idea | — |
| — | CRM ligero | Idea | — |
| — | Inventario / activos | Idea | — |
| — | Tickets internos | Idea | — |
| — | Report builder | Idea | — |

Workspace Fase 2 (import/export Excel de registros, plantillas, API REST de records): [`DynamicWorkspace.md`](DynamicWorkspace.md) §12–§15 — no son apps de menú nuevas.

---

## 4. Criterio para aceptar un vertical nuevo

Antes de `definition_app_*` / rama:

1. ¿Reutiliza `Company` + seguridad + billing?
2. ¿`project_kind` (o capa de plataforma) claro, sin solapar FilePipe / Gate / Match / Pipeline sin diferenciador?
3. ¿Usa esquema dinámico, motor ETL, o es disparador/orquestación?
4. ¿MVP acotado en &lt; 1 fase?
5. ¿No está ya cubierto en §2 de este archivo?

Si 1–4 son sí: doc hijo (estilo [`FILE_GATE.md`](FILE_GATE.md)) → prototipo → implementación.

**Al elegir un ítem del backlog:**

1. Spec en `docs/definition_app_<slug>/` o `.md` de producto.
2. `project_kind` o decisión explícita de capa (Watch/Scheduler/API).
3. Prototipo en `prototype/`.
4. Actualizar **este** índice: mover de §3 a §2 al merge a `main`.

---

*Documento vivo. Lo hecho no se re-propone; el backlog §3 es lo único “por construir o decidir”.*
