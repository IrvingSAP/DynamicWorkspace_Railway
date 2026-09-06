# APP FACTORY — Propuestas de nuevos desarrollos

> **Nombre mnemotécnico:** `APP_FACTORY`  
> Alias: *Propuestas de nuevos desarrollos*  
> Archivo: [`docs/APP_FACTORY.md`](APP_FACTORY.md)

Documento de visión para no perder ideas de aplicativos que se pueden construir **reutilizando el chasis** de DynamicWorkspace + Data Mapping Studio (FilePipe/DMS).

**Fuentes:**

| Documento | Rol |
|-----------|-----|
| [`ESTRUCTURA_PROYECTO.md`](ESTRUCTURA_PROYECTO.md) | Árbol de carpetas, convenciones, checklist |
| [`DynamicWorkspace.md`](DynamicWorkspace.md) | Motor de esquema dinámico (hojas/tablas configurables) |
| [`DataMappingStudio.md`](DataMappingStudio.md) | Motor de transformación de archivos (ETL no-code) |
| [`definition_app_DMS/`](definition_app_DMS/) | Especificación detallada DMS ya implementada en gran parte |

---

## 1. Idea central

La plataforma no es “una sola app”: es un **chasis multi-tenant reutilizable**.

La pieza clave es `Project` con discriminador `project_kind` (`workspace` | `dms` | *futuros*). Todo lo demás ya es transversal:

| Capacidad compartida | Dónde vive |
|----------------------|------------|
| Tenant | `Company` |
| Usuarios y perfiles | `UserProfile` |
| Billing / suscripción | `billing` |
| Seguridad (login, correo, 2FA, Resend) | `security` + `core` |
| Roles por proyecto | `PA` / `ED` / `CO` / `GE` |
| Membresías y auditoría | `projects` + historial |
| Deploy | Railway + PostgreSQL + Resend |

Dos motores de producto:

1. **Motor de esquema dinámico** — `FieldDefinition` + `Record` + `FieldValue` (híbrido) → modelar “hojas” sin código (`project_kind=workspace`).
2. **Motor de transformación** — parse → mapear → reglas → serializar + dry run + versionado → ETL de archivos (`project_kind=dms`).

**Patrón:**

```
Company + Seguridad + Billing + Roles + Auditoría     ← chasis compartido
        │
   Project (project_kind)                             ← discriminador
   ├── workspace  → FieldDefinition / Record / FieldValue
   ├── dms        → Source / Target / Mapping / Rules / Engine
   └── <nuevo>    → próximo vertical (reutiliza chasis ± motores)
```

Cada aplicativo nuevo ≈ un nuevo `project_kind` (o un módulo sobre un kind existente), no un sistema desde cero.

---

## 2. Reutilización alta (mismo motor, poca obra nueva)

> **Propuesta detallada:** [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) (Reverse · Match · Profile Seed · Structure Scout · Catalog · referencia FILE GATE).  
> **Oleada ops / alrededor del archivo:** [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) (Clean · Profiler · Split/Merge · Watch · …; Diff **no app** → Match).

| Aplicativo | Qué reutiliza | Valor |
|------------|---------------|-------|
| **Reverse Studio** (CSV/Excel → posicional / JSON / XML) | DMS “invertido”: mismos perfiles, mapeo y serializadores | Camino inverso ya casi cubierto por el motor actual — ver [`REVERSE_STUDIO.md`](REVERSE_STUDIO.md) |
| **Validador de archivos** (sin transformar) | `SourceProfile` + reglas + reporte de rechazos | Subir → validar esquema → informe OK/errores (bancos, gobierno, intercambio) — ver [`FILE_GATE.md`](FILE_GATE.md) |
| **Conciliador de archivos** | 2 `SourceProfile` + comparación por clave | Cruzar banco vs ERP (u orígenes similares) y reportar diferencias — ver [`FILE_MATCH.md`](FILE_MATCH.md) |
| **Sembrador de perfiles** | Snapshots de SourceProfile / contrato entre apps | Importar estructura ya definida (GATE→Match, etc.) sin re-wizard — ver [`PROFILE_SEED.md`](PROFILE_SEED.md) |
| **Explorador de estructura** | Sample intake + `detection_service` + inferencia de campos/tipos | Proponer patrón/estructura del archivo y sembrar wizards GATE/Reverse/Match — [`STRUCTURE_SCOUT.md`](STRUCTURE_SCOUT.md) · [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) §6 |
| **Catálogos / maestros gestionados** | DynamicWorkspace + `replace_map` / `lookup` | Tablas de referencia que alimentan reglas DMS |

---

## 3. Reutilización media (nuevo `project_kind`, UI propia, misma base)

| Aplicativo | Qué es nuevo | Qué reutiliza |
|------------|--------------|---------------|
| **Formularios / captura no-code** | Vista pública de captura por token | `FieldDefinition` (formulario), `Record` (respuestas), roles, auditoría |
| **Checklists / inspecciones** | Estados + campos tipo foto/adjunto | Esquema dinámico + adjuntos (Fase 3) + historial |
| **CRM / seguimiento ligero** | Vista Kanban por campo “estado” | Records + filtros + membresías |
| **Gestor de activos / inventario** | Campo código + flujos de alta/baja | Import/export Excel + campos dinámicos |
| **Tickets / solicitudes internas** | Workflow de estados | Records + auditoría “quién cambió qué” |

---

## 4. Reutilización de plataforma (mismo tenant; motor o capa nueva)

| Aplicativo | Aprovecha |
|------------|-----------|
| **Programador de transformaciones (scheduling)** | **Hecho** — File Scheduler (`apps.file_scheduler`) — [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) |
| **API / Webhooks de integración** | Ejecución remota de jobs (todas las apps ejecutables) — **[`PLATFORM_API.md`](PLATFORM_API.md)** |
| **Report builder / exportador** | Vistas sobre Records + serializadores DMS (Excel/CSV) |
| **Bandeja de intercambio (carpeta vigilada)** | **Hecho** — File Watch (`apps.file_watch`) — [`FILE_WATCH.md`](FILE_WATCH.md) |

### 4.1 Operaciones de archivo (FILE_OPS) — nueva oleada

Detalle y prioridad: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md).

| Prioridad | Idea | Nota |
|-----------|------|------|
| ⭐⭐⭐⭐⭐ | File Clean | Limpieza pre-Gate; reuso de reglas DMS · **hecho** |
| ⭐⭐⭐⭐⭐ | File Watch | Ingestión automática · **hecho** (M1–M10) |
| ⭐⭐⭐⭐ | Data Profiler / Repair (**pendiente revisión**) · Split/Merge (**hecho**) · Watch / Scheduler (**hecho**) | Ver [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) |
| — | File Convert | **No** como app; modo simple en FilePipe |
| — | File Diff | **No** como app; cubierto por File Match |

### 4.2 FILE PIPELINE — orquestación multi-app

Detalle: [`FILE_PIPELINE.md`](FILE_PIPELINE.md).

Capacidad de plataforma para **componer** pasos (Clean → Merge → Gate → …) con informe OK/Error por etapa. **Hecho** (M1–M5 + tablero). Consumida por UI, Watch, Scheduler y **PLATFORM API**.

### 4.3 PLATFORM API — ejecución remota

Detalle: [`PLATFORM_API.md`](PLATFORM_API.md).

Capa HTTP alineada a las apps **cableadas** y a **pipelines** (`kind=file_pipeline` o atajo `/pipelines/{id}/runs`). Misma semántica que la UI: proyecto/pipeline publicado + archivo(s) → run + informe/salida. Disparador hermano de Watch/Scheduler. Código: `apps.platform_api`.

---

## 5. Prioridad sugerida (esfuerzo / valor)

| Orden | Aplicativo | Estado / nota |
|-------|------------|---------------|
| — | **Validador de archivos** | **Hecho** — [`FILE_GATE.md`](FILE_GATE.md) |
| — | **Reverse Studio** | **Hecho** — [`REVERSE_STUDIO.md`](REVERSE_STUDIO.md) |
| — | **Conciliador de archivos** | **Hecho** — [`FILE_MATCH.md`](FILE_MATCH.md) |
| — | **Explorador de estructura** | **Hecho** — [`STRUCTURE_SCOUT.md`](STRUCTURE_SCOUT.md) |
| — | **Sembrador de perfiles** | **Hecho** (MVP P0 M1–M4) — [`PROFILE_SEED.md`](PROFILE_SEED.md) · [`ps_integration.md`](definition_app_PROFILE_SEED/ps_integration.md) |
| **1** | **Catálogos / maestros** | Propuesta — [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) §5 |
| 3 | **File Clean** (FILE_OPS) | **Hecho** — [`FILE_CLEAN.md`](FILE_CLEAN.md) · [`definition_app_FILE_CLEAN/`](definition_app_FILE_CLEAN/) |
| 3b | **File Split/Merge** (FILE_OPS) | **Hecho** — [`FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) · [`definition_app_FILE_SPLIT_MERGE/`](definition_app_FILE_SPLIT_MERGE/) · `main` / Railway (PR #13) |
| 3c | **Data Profiler** (FILE_OPS) | **Pendiente revisión de aporte** — [`DATA_PROFILER.md`](DATA_PROFILER.md) |
| 3d | **File Repair** (FILE_OPS) | **Pendiente revisión** — [`FILE_REPAIR.md`](FILE_REPAIR.md) (app / modo Gate / Clean) |
| 3e | **Watch + Scheduler** (FILE_OPS) | **Hecho** (M1–M10) — [`FILE_WATCH.md`](FILE_WATCH.md) · [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) · `apps.file_watch` / `apps.file_scheduler` |
| 3f | **Archive / Schema Registry** | **Previsto**; forma TBD — [`FILE_ARCHIVE.md`](FILE_ARCHIVE.md) · [`SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md) |
| 3g | **File Pipeline** (plataforma) | **Hecho** (M1–M5 + tablero) — [`FILE_PIPELINE.md`](FILE_PIPELINE.md) · `apps.file_pipeline` |
| 4 | **Formularios de captura** | Abre el producto a usuarios que no manejan archivos |
| 5 | **PLATFORM API** | **Hecho** (M1–M9) — Job o Pipeline — [`PLATFORM_API.md`](PLATFORM_API.md) · [`definition_app_PLATFORM_API/`](definition_app_PLATFORM_API/) |

> Detalle §2: [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) §1 / §13.  
> Detalle ops: [`APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) §16.

---

## 6. Criterio para aceptar un vertical nuevo

Antes de documentar un vertical en `definition_app_*`, verificar:

1. ¿Reutiliza `Company` + seguridad + billing sin inventar otro tenant?
2. ¿Se modela como `project_kind` (o extensión clara de uno existente)?
3. ¿Usa al menos uno de: esquema dinámico, motor ETL, o ambos?
4. ¿Tiene un MVP acotado (formatos, pantallas, roles) en &lt; 1 fase?
5. ¿No duplica FilePipe ni el workspace de registros sin diferenciador claro?

Si la respuesta es “sí” a 1–4, conviene un doc hermano al estilo `DataMappingStudio.md`.

---

## 7. Próximo paso cuando se elija un vertical

1. Crear `docs/definition_app_<slug>/` o un `.md` de producto (como `DataMappingStudio.md`).
2. Definir módulos, modelo conceptual, casos de uso y fases MVP.
3. Decidir `project_kind` y permisos (mapa a `PA/ED/CO/GE/CG` o paquetes).
4. Prototipar UI en `prototype/` antes de apps Django.
5. Actualizar este archivo marcando el vertical como **en definición** / **en curso** / **hecho**.

---

## 8. Estado de ideas

| Idea | Estado |
|------|--------|
| Validador de archivos | **Hecho (MVP M1–M6)** — [`FILE_GATE.md`](FILE_GATE.md) · `apps/file_gate/` · `main` |
| Reverse Studio | **Hecho (MVP M1–M7 + bridge)** — [`REVERSE_STUDIO.md`](REVERSE_STUDIO.md) · `apps/reverse_studio/` · `main` |
| Conciliador de archivos | **Hecho (MVP M1–M8 + bridge)** — [`FILE_MATCH.md`](FILE_MATCH.md) · `apps/file_match/` · `main` |
| Explorador de estructura | **Hecho (MVP M1–M7)** — [`STRUCTURE_SCOUT.md`](STRUCTURE_SCOUT.md) · `apps/structure_scout/` · `main` |
| Sembrador de perfiles | **Hecho (MVP P0 M1–M4)** — [`PROFILE_SEED.md`](PROFILE_SEED.md) · `apps/profile_seed/` · `main` |
| Catálogos / maestros | **Propuesta detallada** — [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) §5 (`MASTER_CATALOG`) |
| File Clean / Profiler / Split·Merge / Repair | Clean + Split/Merge: **hecho**; Profiler + Repair: **pendiente revisión** — [`DATA_PROFILER.md`](DATA_PROFILER.md), [`FILE_REPAIR.md`](FILE_REPAIR.md); Diff **retirado** |
| File Watch / Scheduler | **Hecho (MVP M1–M10)** — [`FILE_WATCH.md`](FILE_WATCH.md) · [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) · `apps.file_watch` / `apps.file_scheduler` · `main` |
| File Archive / Schema Registry | **Previsto**; forma TBD — [`FILE_ARCHIVE.md`](FILE_ARCHIVE.md), [`SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md) |
| **File Pipeline** (orquestación multi-app) | **Hecho (MVP M1–M5 + tablero)** — [`FILE_PIPELINE.md`](FILE_PIPELINE.md) · `apps.file_pipeline` · `main` |
| **PLATFORM API** (ejecución remota) | **Hecho** (`apps.platform_api`, M1–M9) — Job suelto o Pipeline — [`PLATFORM_API.md`](PLATFORM_API.md) |
| File Convert (app) | **Descartado** como app — modo simple en FilePipe |
| Formularios de captura | Propuesta |
| Checklists / inspecciones | Propuesta |
| CRM ligero | Propuesta |
| Inventario / activos | Propuesta |
| Tickets internos | Propuesta |
| Scheduling DMS | **Cubierto** por File Scheduler (FILE_OPS) — [`FILE_SCHEDULER.md`](FILE_SCHEDULER.md) |
| API / Webhooks | **Hecho** (webhooks M8; YAML OpenAPI aplazado) — [`PLATFORM_API.md`](PLATFORM_API.md) |
| Report builder | Propuesta |
| Bandeja / carpeta vigilada | **Hecho** — File Watch — [`FILE_WATCH.md`](FILE_WATCH.md) |

---

*Documento vivo. Actualizar la tabla §8 cuando una idea pase a definición o implementación.*
