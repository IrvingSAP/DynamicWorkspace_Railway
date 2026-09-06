# DynamicWorkspace — Producto y arquitectura

> Fuente de verdad del **chasis** (tenant, seguridad, workspace dinámico) y del mapa hacia la suite de archivos. Specs por app: `docs/definition_app/` y `definition_app_*`. Inventario de verticales: [`APP_FACTORY.md`](APP_FACTORY.md).

---

## 1. Resumen ejecutivo

**DynamicWorkspace** es una plataforma web **multi-tenant** (compañía, roles, billing, 2FA) con **dos motores** sobre el mismo `Project`:

1. **Esquema dinámico** (`project_kind=workspace`) — proyectos como tablas configurables (campos, registros, auditoría) para sustituir hojas operativas.
2. **Archivos / ETL** (`project_kind=dms` y verticales) — FilePipe (Data Mapping Studio) más Gate, Reverse, Match, Scout, Seed, Clean, Split/Merge, Pipeline, Watch, Scheduler y PLATFORM API.

**Propuesta de valor (workspace):**

> Una plataforma configurable para reemplazar hojas de cálculo operativas dispersas, con control de usuarios, auditoría y estructuras de datos dinámicas.

**Propuesta de valor (archivos):** definir, validar, transformar, conciliar y orquestar archivos sin scripts, reutilizando el mismo login y tenant. Detalle: [`APP_FACTORY.md`](APP_FACTORY.md) · [`DataMappingStudio.md`](DataMappingStudio.md).

| Aspecto | Decisión |
|---------|----------|
| **Producto** | DynamicWorkspace (chasis + workspace + suite de archivos) |
| **Stack** | Python, Django, HTML, JavaScript, CSS (sin Django Forms) |
| **Email** | Resend |
| **Deploy** | Railway + PostgreSQL |
| **Usuarios objetivo** | Equipos operativos (Excel / intercambios de archivo: bancos, ERP, nómina) |

### Documentación relacionada

| Documento | Contenido |
|-----------|-----------|
| [`docs/definition_app/`](definition_app/README.md) | Definición, reglas y diseño por app Django |
| [`docs/definition_app_DMS/`](definition_app_DMS/README.md) | **Data Mapping Studio** — ETL acoplado a la plataforma ([integración](definition_app_DMS/dms_integration.md); origen MVP: [source_definition.md](definition_app_DMS/source_definition.md)) |
| [`docs/ESTRUCTURA_PROYECTO.md`](ESTRUCTURA_PROYECTO.md) | Árbol de carpetas y checklist para nuevos proyectos |
| [`docs/APP_FACTORY.md`](APP_FACTORY.md) | **APP FACTORY** — índice de verticales (hecho vs backlog) |
| [`docs/APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) | Familia §2 reutilización alta (Gate · Reverse · Match · Scout · Seed · Catalog) |
| [`docs/APP_FACTORY_FILE_OPS.md`](APP_FACTORY_FILE_OPS.md) | FILE_OPS: hecho §2 · backlog Profiler / Repair / Archive / Registry |
| [`docs/FILE_CLEAN.md`](FILE_CLEAN.md) | **File Clean** — limpieza/normalización (**hecho**) |
| [`docs/FILE_SPLIT_MERGE.md`](FILE_SPLIT_MERGE.md) | **File Split/Merge** — partición / consolidación (**hecho**) |
| [`docs/DATA_PROFILER.md`](DATA_PROFILER.md) | **Data Profiler** — calidad de contenido (**pendiente revisión**) |
| [`docs/FILE_REPAIR.md`](FILE_REPAIR.md) | **File Repair** — corrección post-Gate (**pendiente revisión**) |
| [`docs/FILE_WATCH.md`](FILE_WATCH.md) | **File Watch** — ingestión por llegada (**hecho**) |
| [`docs/FILE_SCHEDULER.md`](FILE_SCHEDULER.md) | **File Scheduler** — cron / dependencias (**hecho**) |
| [`docs/definition_app_FILE_SCHEDULER/`](definition_app_FILE_SCHEDULER/) | Specs por módulo File Scheduler (M1–M10) |
| [`docs/definition_app_FILE_WATCH/`](definition_app_FILE_WATCH/) | Specs por módulo File Watch (M1–M10) |
| [`docs/FILE_ARCHIVE.md`](FILE_ARCHIVE.md) | **File Archive** — custodia E2E (**previsto**) |
| [`docs/SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md) | **Schema Registry** — contratos compartidos (**previsto**) |
| [`docs/FILE_PIPELINE.md`](FILE_PIPELINE.md) | **File Pipeline** — orquestación multi-app (**hecho**) |
| [`docs/definition_app_FILE_PIPELINE/`](definition_app_FILE_PIPELINE/) | Specs por módulo File Pipeline (M1–M5 + tablero) |
| [`docs/PLATFORM_API.md`](PLATFORM_API.md) | **PLATFORM API** — ejecución remota de jobs/pipelines (**hecho**, M1–M9) |
| [`docs/DataMappingStudio.md`](DataMappingStudio.md) | **FilePipe / DMS** — motor ETL |
| [`docs/FILE_GATE.md`](FILE_GATE.md) | **FILE GATE** — Validador de archivos (**hecho**) |
| [`docs/REVERSE_STUDIO.md`](REVERSE_STUDIO.md) | **Reverse Studio** — Emisor de layouts (**hecho**) |
| [`docs/FILE_MATCH.md`](FILE_MATCH.md) | **FILE MATCH** — Conciliador de archivos (**hecho**) |
| [`docs/STRUCTURE_SCOUT.md`](STRUCTURE_SCOUT.md) | **Structure Scout** — Explorador de estructura (**hecho**) |
| [`docs/PROFILE_SEED.md`](PROFILE_SEED.md) | **Profile Seed** — Sembrador de perfiles (**hecho**) |
| [`docs/definition_app_FILE_GATE/`](definition_app_FILE_GATE/) | Definición por módulo FILE GATE (espejo `definition_app_DMS`) |
| [`docs/definition_app/UI_MESSAGES.md`](definition_app/UI_MESSAGES.md) | Catálogo de mensajes UI, `error_code`, reglas vista/servicio |
| [`docs/definition_app/DynamicWorkspace_Model.md`](definition_app/DynamicWorkspace_Model.md) | Modelos de datos, relaciones e integridad |
| [`docs/security/SEGURIDAD_Y_ACCESOS.md`](security/SEGURIDAD_Y_ACCESOS.md) | Flujos de login, correo, 2FA |
| [`docs/security/GUIA_IMPLEMENTACION_SEGURIDAD.md`](security/GUIA_IMPLEMENTACION_SEGURIDAD.md) | Implementación técnica de seguridad |
| [`docs/definition_app/public.md`](definition_app/public.md) | Sitio público y guía `/ayuda/` |
| [`docs/definition_app/help.md`](definition_app/help.md) | Guía de flujos UF `/app/ayuda/` |

---

## 2. Problema que resuelve

Los equipos crean archivos Excel para:

- Controles de actividades
- Gestiones operativas con poca extensión de datos
- Seguimiento ad hoc sin sistema formal

**Limitaciones actuales de Excel:**

- Sin control centralizado de acceso por rol
- Sin auditoría fiable de quién cambió qué
- Estructuras duplicadas y dispersas
- Dificultad para filtrar, buscar y escalar
- Versiones locales sin fuente única de verdad

**Objetivo:** un sistema donde cada equipo defina su propia “hoja” sin tocar código, con permisos, historial y búsqueda.

---

## 3. Concepto central

```mermaid
flowchart TB
    subgraph system [DynamicWorkspace]
        Users[Usuarios y permisos globales]
        subgraph projA [Proyecto A]
            FA[Campo Nombre]
            FB[Campo Fecha]
            FC[Campo Estado]
            RA[Registros]
        end
        subgraph projB [Proyecto B]
            FD[Campo Cliente]
            FE[Campo Monto]
            FF[Campo Vencimiento]
            RB[Registros]
        end
    end
    Users --> projA
    Users --> projB
    FA --> RA
    FB --> RA
    FC --> RA
    FD --> RB
    FE --> RB
    FF --> RB
```

Cada **proyecto workspace** = una tabla configurable independiente:

1. El administrador define campos (tipo, longitud, validaciones, obligatoriedad).
2. Se asignan usuarios con roles.
3. Los usuarios crean, consultan, editan y filtran **registros** según esa estructura.
4. Dos proyectos pueden tener estructuras completamente distintas sin cambiar el código.

El mismo `Project` admite otros `project_kind` (FilePipe, Gate, Match, …): no usan `Record`/`FieldValue` como tabla de negocio; usan perfiles DMS, jobs e informes. Ver [`APP_FACTORY.md`](APP_FACTORY.md).

---

## 4. Alcance funcional (motor workspace)

El alcance de **archivos** (FilePipe y verticales) está en [`APP_FACTORY.md`](APP_FACTORY.md), [`DataMappingStudio.md`](DataMappingStudio.md) y los `FILE_*.md`. Esta sección describe el workspace de registros.

### 4.1 Gestión de proyectos

| Función | Descripción |
|---------|-------------|
| Crear proyecto | Nombre, descripción, icono/color opcional |
| Configurar campos | Definición dinámica del esquema |
| Asignar usuarios | Invitar o autorizar por email |
| Archivar proyecto | Ocultar sin borrar datos |
| Plantilla de proyecto | Duplicar estructura de campos (mejora propuesta) |

### 4.2 Gestión de registros

| Función | Descripción |
|---------|-------------|
| CRUD | Crear, leer, actualizar, eliminar (soft delete recomendado) |
| Listado paginado | Tabla tipo Excel con columnas del proyecto |
| Filtros | Por campo, operadores según tipo |
| Búsqueda | Texto libre en campos de texto |
| Ordenamiento | Por cualquier columna visible |
| Exportar Excel | Simetría con importación (mejora propuesta) |

### 4.3 Importación desde Excel

Flujo crítico para adopción:

```
Excel existente → Análisis de columnas → Creación automática de campos → Carga de registros
```

- Detección de tipos (texto, número, fecha)
- Mapeo manual de columnas si hace falta
- Vista previa antes de confirmar
- Reporte de filas con error

### 4.4 Auditoría e historial

| Dato | Nivel |
|------|-------|
| Quién creó el registro | Registro |
| Quién modificó | Registro + por campo |
| Fecha creación / modificación | Registro |
| Valor anterior | Historial de cambios por campo |

Pregunta que el sistema debe responder: *¿Quién cambió este valor y cuándo?*

---

## 5. Tipos de campo — implementación por fases

### Fase MVP (imprescindible)

| Tipo | Validaciones |
|------|--------------|
| Texto corto | Longitud máxima |
| Texto largo | Longitud máxima |
| Número entero | Rango min/max |
| Decimal | Rango, decimales |
| Fecha | Formato, rango |
| Fecha y hora | Formato, rango |
| Sí/No | Booleano |
| Lista desplegable | Opciones definidas en el campo |

### Fase 2

| Tipo | Notas |
|------|-------|
| Selección múltiple | Array de opciones |
| Correo electrónico | Formato + unicidad opcional |
| Teléfono | Máscara / formato |
| URL | Validación de formato |
| Estado | Lista con colores (workflow ligero) |

### Fase 3

| Tipo | Notas |
|------|-------|
| Archivo adjunto | Almacenamiento en Railway/S3 |
| Imagen | Preview en listado |
| Usuario responsable | FK a usuario del proyecto |
| Etiquetas | Tags libres o predefinidos |
| Campo calculado | Fórmulas simples entre campos numéricos/fechas |

---

## 6. Seguridad y accesos (resumen)

La seguridad se documenta en **`docs/security/`**. Aquí solo el resumen; el detalle de flujos, modelos e implementación está en los documentos enlazados.

### Tipos de usuario global

| Código | Rol | Alcance principal |
|--------|-----|-------------------|
| `UA` | User Admin | Configuración del sistema |
| `US` | User System | Crear usuarios UF, gestionar usuarios de proyecto, auditoría |
| `UF` | User Final | Crear proyectos; autorizar usuarios al proyecto |

### Roles por proyecto

| Rol | Permisos principales |
|-----|----------------------|
| `PA` — Admin de proyecto | Diseñar estructura, gestionar miembros, auditoría |
| `ED` — Editor | Crear y modificar registros |
| `CO` — Consulta | Solo lectura |
| `GE` — Generar | Exportar a otros formatos |
| `CG` — Consulta-Generar | Consulta del proyecto y generar / exportar salidas |

**Reglas clave:**

- **Compañía** es el tenant principal; todo usuario y proyecto pertenece a una compañía.
- Sin registro público: **UA/US** crean cuentas (con compañía asignada).
- Login con contraseña + **2FA (TOTP)** + verificación por correo en primer acceso.
- US/UF requieren **suscripción vigente** de la compañía para acceder a `/app/`.
- Sin membresía al proyecto → sin acceso a datos del proyecto.

**Documentación completa:**

- Compañía: [`definition_app/company.md`](definition_app/company.md)
- Billing: [`definition_app/billing.md`](definition_app/billing.md)
- Flujos: [`security/SEGURIDAD_Y_ACCESOS.md`](security/SEGURIDAD_Y_ACCESOS.md)
- Implementación: [`security/GUIA_IMPLEMENTACION_SEGURIDAD.md`](security/GUIA_IMPLEMENTACION_SEGURIDAD.md)
- Modelos usuario: [`definition_app/accounts.md`](definition_app/accounts.md) · [`definition_app/DynamicWorkspace_Model.md`](definition_app/DynamicWorkspace_Model.md#userprofile)
- Aprovisionamiento masivo UF (pendiente Fase 1+): [`definition_app/accounts_provisioning.md`](definition_app/accounts_provisioning.md)
- Permisos por proyecto: [`definition_app/projects.md`](definition_app/projects.md) · [`definition_app/DynamicWorkspace_Model.md`](definition_app/DynamicWorkspace_Model.md#projectmembership)

---

## 7. Arquitectura de datos — evaluación y recomendación

### Opciones analizadas

| Opción | Ventajas | Desventajas |
|--------|----------|-------------|
| **EAV puro** | Máxima flexibilidad; consultas por tipo | Consultas complejas; muchas filas por registro |
| **JSON por registro** | Simple de implementar; esquema flexible | Filtrado/indexado más costoso sin PostgreSQL JSONB |
| **Columnas dinámicas reales** | Consultas SQL rápidas | Requiere migrar DDL al cambiar campos; no recomendado |
| **Híbrido (recomendado)** | Metadatos relacionales + valores flexibles | Algo más de diseño inicial |

### Recomendación: modelo híbrido

Detalle de entidades y campos en [`definition_app/DynamicWorkspace_Model.md`](definition_app/DynamicWorkspace_Model.md).

```mermaid
erDiagram
    Company ||--o{ UserProfile : usuarios
    Company ||--o{ Project : proyectos
    Company ||--|| Subscription : licencia
    User ||--o| UserProfile : profile
    Project ||--o{ FieldDefinition : define
    Project ||--o{ Record : contiene
    Record ||--o{ FieldValue : almacena
```

Diagrama completo en [`definition_app/DynamicWorkspace_Model.md`](definition_app/DynamicWorkspace_Model.md).

**Por qué híbrido:**

1. **`FieldDefinition`** en tablas relacionales → UI, validación y permisos estables.
2. **`FieldValue`** con columnas tipadas (`value_text`, `value_number`, etc.) → filtros eficientes en PostgreSQL.
3. **`value_json`** como respaldo para tipos compuestos (selección múltiple, etiquetas).
4. Evita alterar el esquema SQL cada vez que un usuario añade un campo.

**Base de datos en producción:** PostgreSQL en Railway (no SQLite). SQLite solo para desarrollo local.

**Mejora propuesta:** versionar el esquema de campos (`FieldDefinition.version`). Si se cambia el tipo de un campo, los registros antiguos conservan historial y se valida la migración de datos.

---

## 8. Arquitectura de aplicación (Django)

Detalle por app en [`definition_app/`](definition_app/README.md).

```
apps/
├── core/              # Utilidades, permisos, correo
├── company/           # Company (tenant principal)
├── billing/           # Plan, Subscription, Payment
├── accounts/          # Usuarios, UserProfile + company
├── security/          # Login, correo, 2FA
├── dashboard/         # Home y bienvenida
├── public/            # Sitio público (inicio, servicios, contacto, guía)
├── help/              # Guía de flujos UF (/app/ayuda/)
├── projects/          # Proyecto por compañía, membresías, project_kind
├── fields/            # FieldDefinition, validadores (workspace)
├── records/           # Record, FieldValue, CRUD (workspace)
├── dms/               # FilePipe / Data Mapping Studio — ver DataMappingStudio.md
├── file_gate/         # File Gate — hecho — FILE_GATE.md
├── reverse_studio/    # Reverse Studio — hecho — REVERSE_STUDIO.md
├── file_match/        # File Match — hecho — FILE_MATCH.md
├── structure_scout/   # Structure Scout — hecho — STRUCTURE_SCOUT.md
├── profile_seed/      # Profile Seed — hecho — PROFILE_SEED.md
├── file_clean/        # File Clean — hecho — FILE_CLEAN.md
├── file_split_merge/  # File Split/Merge — hecho — FILE_SPLIT_MERGE.md
├── file_pipeline/     # File Pipeline — hecho — FILE_PIPELINE.md
├── file_scheduler/    # File Scheduler — hecho — FILE_SCHEDULER.md
├── file_watch/        # File Watch — hecho — FILE_WATCH.md
└── platform_api/      # PLATFORM API — hecho — PLATFORM_API.md
```

`audit` e `imports` (Excel → workspace) están especificados en [`definition_app/`](definition_app/README.md); **no** son apps en `INSTALLED_APPS` hoy. Auditoría de registros vive con `records`; importación Excel del workspace = Fase 2.

**Modelo tenant:** `Company` → usuarios (`UserProfile`) → proyectos → registros **o** mapeos DMS (`project_kind`). Ver [`definition_app/DynamicWorkspace_Model.md`](definition_app/DynamicWorkspace_Model.md).

### Convenciones técnicas (ya definidas)

- Formularios en **HTML plano**; procesamiento en vistas con validación manual.
- **Sin Django Forms** (`forms.py`, `ModelForm`).
- JavaScript en `static/js/` para filtros, tablas dinámicas y UX tipo hoja de cálculo.
- Resend para invitaciones y notificaciones.
- WhiteNoise + Gunicorn en Railway (`gthread`, `CONN_MAX_AGE=600`).
- Producción: `DJANGO_SETTINGS_MODULE=dynamicworkspace.production` — detalle en [`README.md`](../README.md) § Deploy Railway.

### Flujo de una petición

```mermaid
sequenceDiagram
    participant U as Usuario
    participant V as Vista Django
    participant S as Servicio
    participant DB as PostgreSQL

    U->>V: POST registro HTML
    V->>S: validate_record(project, data)
    S->>DB: leer FieldDefinition
    S->>S: validar tipos y reglas
    S->>DB: guardar Record + FieldValue
    S->>DB: escribir RecordHistory
    V->>U: respuesta HTML / redirect
```

---

## 9. Interfaz de usuario (visión)

| Pantalla | Descripción |
|----------|-------------|
| Dashboard | Proyectos del usuario, accesos recientes |
| Diseñador de campos | Drag-and-drop o lista ordenable de campos |
| Vista de registros | Tabla editable tipo Excel, filtros en cabecera |
| Detalle de registro | Formulario HTML + panel de historial |
| Gestión de usuarios | Tabla de miembros y roles del proyecto |
| Importar | Wizard: subir Excel → mapear → confirmar |

**Mejora propuesta:** vista de “tarjetas” opcional además de tabla, para proyectos con pocos campos.

---

## 10. Requisitos no funcionales

| Requisito | Objetivo |
|-----------|----------|
| Seguridad | Ver [`security/`](security/) — CSRF, sesión, 2FA, permisos por proyecto |
| Rendimiento | Paginación; índices en `project_id`, `field_id`, columnas tipadas |
| Escalabilidad | Límites configurables: campos por proyecto, registros por proyecto |
| Disponibilidad | Railway con health check |
| Backup | Backups automáticos de PostgreSQL en Railway |
| Accesibilidad | Formularios HTML semánticos, contraste, teclado |

---

## 11. Mejoras propuestas sobre el contexto original

| # | Mejora | Justificación |
|---|--------|---------------|
| 1 | **PostgreSQL + modelo híbrido** en lugar de solo EAV o solo JSON | Balance entre flexibilidad y rendimiento de filtros |
| 2 | **Soft delete** en registros | Recuperación ante borrados accidentales |
| 3 | **Exportar a Excel** | Paridad con importación; facilita transición |
| 4 | **Plantillas de proyecto** | Reutilizar estructuras comunes sin redefinir campos |
| 5 | **Versionado de esquema** | Cambios de campo sin romper datos históricos |
| 6 | **Invitaciones por email** (Resend) | Onboarding de usuarios al proyecto |
| 7 | **Límites por plan** | Evitar proyectos con miles de campos que degraden UX |
| 8 | **Campos calculados en Fase 3** | Reducir fórmulas manuales que hoy viven en Excel |
| 9 | **API REST de records (Fase 3)** | Distinta de **PLATFORM API** (jobs/pipelines, **hecho**) |
| 10 | **Búsqueda guardada** | Filtros frecuentes (“Estado=Pendiente”) como vistas |

---

## 12. Roadmap sugerido

### Fase 0 — Fundación — **hecho**

- [x] Proyecto Django inicializado
- [x] Estructura de carpetas y reglas Cursor
- [x] Autenticación, compañía, billing y CRUD usuarios (ver [`definition_app/company.md`](definition_app/company.md), [`definition_app/billing.md`](definition_app/billing.md), [`definition_app/accounts.md`](definition_app/accounts.md))
- [x] Modelo `Project`, `FieldDefinition`, `Record`, `FieldValue`

> **Pendiente (no bloquea el chasis):** aprovisionamiento masivo UF — [`definition_app/accounts_provisioning.md`](definition_app/accounts_provisioning.md)

### Fase 1 — MVP workspace — **hecho**

- [x] CRUD de proyectos y campos (tipos básicos)
- [x] CRUD de registros con tabla HTML + JS
- [x] Roles por proyecto: PA, ED, CO, GE (ver [`definition_app/projects.md`](definition_app/projects.md))
- [x] Auditoría básica (creado por, modificado por, fechas)
- [x] Deploy en Railway + PostgreSQL

La **suite de archivos** se construyó **en paralelo** sobre este chasis. Inventario: [`APP_FACTORY.md`](APP_FACTORY.md) §2.

### Fase 2 — Adopción (workspace)

- Importación desde Excel (`apps.imports` — spec, no app aún)
- Exportación a Excel
- Filtros y búsqueda avanzada
- Historial de cambios por campo
- Invitaciones por email (Resend) — el canal de correo **sí** existe (seguridad); invitaciones de **proyecto** pueden seguir abiertas

### Fase 3 — Madurez (workspace)

- Tipos de campo avanzados (archivos, imágenes, calculados)
- Plantillas de proyecto
- Permisos por campo
- API REST de **registros** (no confundir con PLATFORM API de jobs)
- Notificaciones y workflows de estado

**Fábrica aún abierta:** Master Catalog; revisión Profiler/Repair; File Archive; Schema Registry. Ver [`APP_FACTORY.md`](APP_FACTORY.md).

---

## 13. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Cambiar tipo de campo rompe datos | Versionado de esquema + reglas de migración |
| Filtros lentos con muchos registros | Índices, paginación, columnas tipadas en `FieldValue` |
| Expectativa “igual que Excel” | UX de tabla editable + import/export desde el MVP |
| Complejidad del diseñador de campos | Empezar con lista ordenable; drag-and-drop en Fase 2 |
| Sin Django Forms → más código manual | Capa de servicios `validators/` reutilizable por tipo |

---

## 14. Métricas de éxito

| Métrica | Meta inicial |
|---------|--------------|
| Tiempo de crear un proyecto con 5 campos | < 5 minutos |
| Importar Excel de 100 filas | < 2 minutos |
| Usuarios activos por proyecto | ≥ 2 en pilotos |
| Adopción | ≥ 1 proyecto por equipo piloto en 30 días |

---

## 15. Próximos pasos

El chasis y el MVP workspace **están hechos**. Prioridad de producto (fábrica):

1. **Master Catalog** — siguiente vertical §2 — [`APP_FACTORY_HIGH_REUSE.md`](APP_FACTORY_HIGH_REUSE.md) §5.
2. **Revisión Profiler / Repair** — ¿app o no? — [`DATA_PROFILER.md`](DATA_PROFILER.md) · [`FILE_REPAIR.md`](FILE_REPAIR.md).
3. **File Archive / Schema Registry** — previstos — [`FILE_ARCHIVE.md`](FILE_ARCHIVE.md) · [`SCHEMA_REGISTRY.md`](SCHEMA_REGISTRY.md).
4. **Workspace Fase 2** — import/export Excel de registros, historial por campo (si se prioriza el motor de hojas).
5. **Aprovisionamiento masivo UF** — [`definition_app/accounts_provisioning.md`](definition_app/accounts_provisioning.md).

---

*Documento: `docs/DynamicWorkspace.md` — DynamicWorkspace*
