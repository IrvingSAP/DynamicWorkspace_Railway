# definition_app — Definición de aplicaciones Django

Documentación segregada por **app**: responsabilidades, modelos, reglas, diseño y fases de implementación.

## Índice de apps

| App | Documento | Fase | Estado |
|-----|-----------|------|--------|
| `apps.core` | [`core.md`](core.md) | 0 | Definido |
| `apps.company` | [`company.md`](company.md) | 0 | Definido |
| `apps.billing` | [`billing.md`](billing.md) | 0 | Definido |
| `apps.accounts` | [`accounts.md`](accounts.md) | 0 | Definido · [batch UF](accounts_provisioning.md) pendiente Fase 1+ |
| `apps.security` | [`security.md`](security.md) | 0 | Definido |
| `apps.dashboard` | [`dashboard.md`](dashboard.md) | 0 | Definido |
| `apps.public` | [`public.md`](public.md) | 0 | Implementado (guía Fase 1) |
| `apps.help` | [`help.md`](help.md) | 1 | Implementado |
| `apps.projects` | [`projects.md`](projects.md) | 1 | Definido |
| `apps.fields` | [`fields.md`](fields.md) | 1 | Definido |
| `apps.records` | [`records.md`](records.md) | 1 | Definido |
| `apps.audit` | [`audit.md`](audit.md) | 1 | Definido |
| `apps.imports` | [`imports.md`](imports.md) | 2 | Definido |
| `apps.dms` | [`../definition_app_DMS/README.md`](../definition_app_DMS/README.md) · [origen](../definition_app_DMS/source_definition.md) · [destino](../definition_app_DMS/target_definition.md) | 1+ | Parcial — SourceProfile + TargetProfile MVP; mapeo/ejecución pendientes |

## Convenciones globales

| Documento | Contenido |
|-----------|-----------|
| [`CONVENCIONES.md`](CONVENCIONES.md) | Reglas transversales resumidas |
| [`VISTAS.md`](VISTAS.md) | Reglas globales para vistas Python |
| [`UI_MESSAGES.md`](UI_MESSAGES.md) | **Reglas obligatorias** — mensajes UI, `error_code`, vista/servicio/template |
| [`PROTOTIPOS.md`](PROTOTIPOS.md) | Flujo de prototipos HTML (`prototype/`) |
| [`records_datatables_design.md`](records_datatables_design.md) | Diseño DataTables tipo hoja de cálculo (`apps.records`) |
| [`accounts_provisioning.md`](accounts_provisioning.md) | Carga masiva UF por CSV (**pendiente** Fase 1+) |

## Modelos de datos

Ver [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md) — documento maestro con campos, relaciones, choices e integridad referencial.

## Otras carpetas de documentación

| Carpeta | Contenido |
|---------|-----------|
| [`../DynamicWorkspace.md`](../DynamicWorkspace.md) | Visión de producto y arquitectura general |
| [`../definition_app_DMS/`](../definition_app_DMS/README.md) | Data Mapping Studio (ETL) — integrado a la plataforma |
| [`../security/`](../security/) | Flujos de autenticación, 2FA e implementación |

## Plantilla para nuevas apps

Cada documento de app incluye:

1. **Propósito** — qué resuelve la app
2. **Responsabilidades** — qué hace y qué no hace
3. **Modelos** — entidades y relaciones
4. **Vistas y URLs** — endpoints previstos
5. **Reglas** — convenciones específicas
6. **Dependencias** — otras apps que consume
7. **Fase** — cuándo se implementa
