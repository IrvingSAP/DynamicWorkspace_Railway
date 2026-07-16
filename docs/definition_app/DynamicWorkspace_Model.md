# DynamicWorkspace — Modelos y relaciones

Documento maestro de entidades de datos. Fuente de verdad para campos, relaciones, choices y reglas de negocio a nivel modelo.

**Convenciones:**

- Stack: **Python**, **Django**, **PostgreSQL** (producción), HTML/CSS/JS — ver [`../DynamicWorkspace.md`](../DynamicWorkspace.md).
- Apps bajo `apps/` (p. ej. `apps.company`, `apps.accounts`, `apps.projects`).
- PKs con **UUID** en modelos de dominio (compañía, proyectos, registros).
- **Tenant principal:** `Company` — todo `UserProfile` y todo `Project` pertenecen a una compañía.
- Aislamiento: datos filtrados por `profile.company` + `ProjectMembership`.
- Referencia funcional de seguridad: [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md).

### Jerarquía tenant

```
Company
 ├── UserProfile (usuarios)
 ├── Subscription (licencia)
 └── Project
      ├── FieldDefinition
      └── Record → FieldValue
```

**Flujo de contexto en vistas:**

`request.user` → `user.profile` → `profile.company` → `company.subscription` (licencia)

---

## Índice de modelos

| Modelo | App | Fase | Estado | Definición app |
|--------|-----|------|--------|----------------|
| [User](#user-django-auth) | `django.contrib.auth` | 0 | Definido | [`accounts.md`](accounts.md) |
| [Company](#company) | `apps.company` | 0 | Definido | [`company.md`](company.md) |
| [UserProfile](#userprofile) | `apps.accounts` | 0 | Definido | [`accounts.md`](accounts.md) |
| [Plan](#plan) | `apps.billing` | 0 | Definido | [`billing.md`](billing.md) |
| [Subscription](#subscription) | `apps.billing` | 0 | Definido | [`billing.md`](billing.md) |
| [SubscriptionContact](#subscriptioncontact) | `apps.billing` | 0 | Definido | [`billing.md`](billing.md) |
| [Payment](#payment) | `apps.billing` | 0 | Definido | [`billing.md`](billing.md) |
| [Project](#project) | `apps.projects` | 1 | Definido | [`projects.md`](projects.md) |
| [ProjectMembership](#projectmembership) | `apps.projects` | 1 | Definido | [`projects.md`](projects.md) |
| [FieldDefinition](#fielddefinition) | `apps.fields` | 1 | Definido | [`fields.md`](fields.md) |
| [Record](#record) | `apps.records` | 1 | Definido | [`records.md`](records.md) |
| [FieldValue](#fieldvalue) | `apps.records` | 1 | Definido | [`records.md`](records.md) |
| [RecordHistory](#recordhistory) | `apps.audit` | 1 | Definido | [`audit.md`](audit.md) |
| [DmsProjectConfig](#dms-modelos-appsdms) | `apps.dms` | 1+ | Parcial (código) | [`../definition_app_DMS/dms_integration.md`](../definition_app_DMS/dms_integration.md) |
| [DmsMappingVersion](#dms-modelos-appsdms) | `apps.dms` | 1+ | Parcial (código) | [`../definition_app_DMS/project_lifecycle.md`](../definition_app_DMS/project_lifecycle.md) |
| [DmsSourceProfile](#dms-modelos-appsdms) | `apps.dms` | 1+ | **MVP origen** | [`../definition_app_DMS/source_definition.md`](../definition_app_DMS/source_definition.md) |
| [DmsTargetProfile](#dms-modelos-appsdms) | `apps.dms` | 1+ | **MVP destino** | [`../definition_app_DMS/target_definition.md`](../definition_app_DMS/target_definition.md) |
| Catálogos DMS | `apps.dms` | 1+ | Parcial (CRUD + semillas) | [`../definition_app_DMS/system_catalogs.md`](../definition_app_DMS/system_catalogs.md) |

> Modelos planificados Fase 2: `ImportJob` (`apps.imports`) — ver [`imports.md`](imports.md).  
> **Data Mapping Studio:** documentación en [`../definition_app_DMS/`](../definition_app_DMS/README.md); no usa `FieldDefinition` / `Record`.

---

## Diagrama de relaciones

```mermaid
erDiagram
    Company ||--o{ UserProfile : usuarios
    Company ||--o{ Project : proyectos
    Company ||--|| Subscription : licencia
    User ||--o| UserProfile : profile
    User ||--o{ Company : created_updated_by
    Plan ||--o{ Subscription : plan
    Subscription ||--o{ SubscriptionContact : contactos
    Subscription ||--o{ Payment : pagos
    User ||--o{ Project : owner
    User ||--o{ ProjectMembership : participa
    User ||--o{ Record : crea
    User ||--o{ RecordHistory : audita
    Project ||--o{ ProjectMembership : incluye
    Project ||--o{ FieldDefinition : define
    Project ||--o{ Record : contiene
    Record ||--o{ FieldValue : almacena
    Record ||--o{ RecordHistory : historial
    FieldDefinition ||--o{ FieldValue : tipa
    FieldDefinition ||--o{ RecordHistory : campo

    Company {
        uuid id PK
        string name_short UK
        string name_long
        bool is_active
    }

    UserProfile {
        uuid id PK
        uuid user_id FK
        uuid company_id FK
        string user_type
        bool email_confirmed
        bool tfa_verified
    }

    Plan {
        uuid id PK
        string code UK
        string name
        string billing_period
    }

    Subscription {
        uuid id PK
        uuid company_id FK UK
        uuid plan_id FK
        date start_date
        date end_date
        string status
    }

    Project {
        uuid id PK
        uuid company_id FK
        string name
        string slug
        uuid owner_id FK
    }
```

---

## User (Django auth)

**App:** `django.contrib.auth`  
**Tabla:** `auth_user`  
**Documento app:** [`accounts.md`](accounts.md)

Cuenta de autenticación estándar de Django. No se extiende el modelo; el perfil vive en `UserProfile`.

### Campos relevantes para DynamicWorkspace

| Campo | Tipo Django | Null | Descripción |
|-------|-------------|------|-------------|
| `id` | AutoField / UUID* | No | PK |
| `username` | CharField(150) | No | Login único |
| `email` | EmailField | Sí | Verificación por correo y notificaciones (Resend) |
| `password` | CharField(128) | No | Hash Django |
| `first_name` | CharField(150) | Sí | Nombre (opcional) |
| `last_name` | CharField(150) | Sí | Apellido (opcional) |
| `is_active` | BooleanField | No | `True` por defecto |
| `is_staff` | BooleanField | No | Acceso Django admin (opcional para UA) |
| `is_superuser` | BooleanField | No | Superusuario técnico |
| `date_joined` | DateTimeField | No | Fecha de alta |

\* Valorar UUID en fase de implementación; Django por defecto usa entero autoincremental.

### Reglas

1. `username` y `email` únicos.
2. Sin `email` no se completa el flujo de verificación por correo.
3. Alta solo por UA/US; no hay registro público.
4. Todo usuario creado debe asignarse a una `Company` en `UserProfile`.

---

## Company

**App:** `apps.company`  
**Tabla:** `company_company`  
**Documento app:** [`company.md`](company.md)

Modelo **tenant principal**. Agrupa usuarios, proyectos y suscripción.

### Relaciones

| Relación | Modelo | Cardinalidad | Notas |
|----------|--------|--------------|-------|
| `user_profiles` | `UserProfile` | 1:N | `related_name="user_profiles"` |
| `projects` | `Project` | 1:N | `related_name="projects"` |
| `subscription` | `Subscription` | 1:1 | `related_name="subscription"` |
| `created_by` | `auth.User` | N:1 | `SET_NULL`, `related_name="companies_created"` |
| `updated_by` | `auth.User` | N:1 | `SET_NULL`, `related_name="companies_updated"` |

### Campos

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `id` | UUIDField | No | uuid4 | PK |
| `name_short` | CharField(15) | No | — | Código o sigla única |
| `name_long` | CharField(150) | No | — | Nombre completo |
| `tax_id` | CharField(50) | Sí | — | Identificación tributaria |
| `address` | CharField(255) | Sí | — | Dirección |
| `phone` | CharField(50) | Sí | — | Teléfono |
| `email` | EmailField | Sí | — | Correo de contacto |
| `logo` | ImageField | Sí | — | `upload_to="company_logos/"` |
| `is_active` | BooleanField | No | `True` | Compañía activa |
| `created_at` | DateTimeField | No | auto_now_add | — |
| `updated_at` | DateTimeField | No | auto_now | — |
| `created_by` | ForeignKey → User | Sí | — | Auditoría |
| `updated_by` | ForeignKey → User | Sí | — | Auditoría |

### Reglas de negocio

1. `name_short` único globalmente.
2. No eliminar compañía con usuarios, proyectos o suscripción (`PROTECT` / servicio de borrado).
3. Solo **UA** administra compañías a nivel plataforma.
4. Usuarios **US** y **UF** operan dentro de la compañía asignada en su perfil.

### Meta (Django)

```python
class Meta:
    verbose_name = "Compañía"
    verbose_name_plural = "Compañías"
    ordering = ["name_short"]
```

---

## UserProfile

**App:** `apps.accounts`  
**Tabla:** `accounts_userprofile`  
**Relación:** OneToOne con `auth.User`  
**Acceso en código:** `user.profile` / `request.user.profile`  
**Documento app:** [`accounts.md`](accounts.md)

Extiende la cuenta con **compañía obligatoria**, tipo de usuario global (UA/US/UF) y flags de seguridad (correo + 2FA). Se crea al crear un `User` (signal `post_save`); la compañía se asigna en el alta por UA/US.

### Relaciones

| Relación | Modelo | Cardinalidad | Notas |
|----------|--------|--------------|-------|
| `user` | `auth.User` | 1:1 | Obligatorio, `on_delete=CASCADE`, `related_name="profile"` |
| `company` | `Company` | N:1 | **Obligatorio**, `on_delete=PROTECT`, `related_name="user_profiles"` |
| `created_by` | `auth.User` | N:1 | `SET_NULL`, `related_name="created_profiles"` |
| `updated_by` | `auth.User` | N:1 | `SET_NULL`, `related_name="updated_profiles"` |

### Campos — enlace y tenant

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `id` | UUIDField | No | uuid4 | PK |
| `user` | OneToOneField → User | No | — | Cuenta Django asociada |
| `company` | ForeignKey → Company | **No** | — | Compañía del usuario (obligatorio) |

### Campos — tipo de usuario

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `user_type` | CharField(2) | No | `"UF"` | Rol global del sistema |

**Valores permitidos (`user_type`):**

| Código | Constante | Nombre | Descripción |
|--------|-----------|--------|-------------|
| `UA` | `USER_ADMIN` | User Admin | Administrador del sistema; configuración global |
| `US` | `USER_SYSTEM` | User System | Crea usuarios UF; gestión y auditoría de proyectos |
| `UF` | `USER_FINAL` | User Final | Crea proyectos; autoriza miembros |

**Alcance por tipo:**

| Capacidad | UA | US | UF |
|-----------|----|----|-----|
| Crear usuarios UA | No | No | No |
| Crear usuarios US | Sí | No | No |
| Crear usuarios UF | No | Sí | No |
| Crear proyectos | Configurable | Configurable | Sí |
| Configuración sistema | Sí | Parcial | No |

### Campos — seguridad (correo y 2FA)

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `email_confirmed` | BooleanField | No | `False` | Correo verificado en onboarding |
| `email_confirm_code` | CharField(6) | Sí | — | Código enviado por correo (6 dígitos) |
| `email_confirm_exp` | DateTimeField | Sí | — | Caducidad del código (+5 min) |
| `totp_secret` | CharField(64) | Sí | — | Secreto TOTP en base32 (pyotp) |
| `tfa_verified` | BooleanField | No | `False` | 2FA completado al menos una vez |
| `last_totp_reset` | DateTimeField | Sí | — | Último reset de autenticador |

### Campos — control de cuenta

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `status` | CharField(1) | No | `"A"` | `A` = activo, `I` = inactivo |
| `locked_until` | DateTimeField | Sí | — | Bloqueo temporal tras intentos fallidos |
| `primer_acceso_completado` | BooleanField | No | `False` | `True` tras primera visita a `/app/bienvenida/` |

### Campos — auditoría

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `created_at` | DateTimeField | No | auto_now_add | Alta del perfil |
| `updated_at` | DateTimeField | No | auto_now | Última modificación |
| `created_by` | ForeignKey → User | Sí | — | Quién creó el perfil |
| `updated_by` | ForeignKey → User | Sí | — | Quién actualizó el perfil |

### Propiedades (lógica, no columnas)

| Nombre | Retorno | Descripción |
|--------|---------|-------------|
| `is_security_complete` | bool | `email_confirmed` ∧ `tfa_verified` ∧ `totp_secret` no vacío |
| `is_active_account` | bool | `status == "A"` y (`locked_until` es null o expiró) |
| `can_create_users` | bool | `user_type in ("UA", "US")` |
| `can_create_projects` | bool | `user_type == "UF"` y compañía activa |
| `can_access_app` | bool | `is_security_complete` ∧ `is_active_account` ∧ suscripción vigente (US/UF) |

### Estados de seguridad

| Estado | Condición |
|--------|-----------|
| Registrado | Perfil recién creado; `email_confirmed` y `tfa_verified` en `False` |
| Correo pendiente | `email_confirmed = False` |
| TOTP pendiente | `email_confirmed = True`, `tfa_verified = False` |
| Activo (seguridad) | `is_security_complete = True` |
| Re-enrolamiento | Tras reset 2FA: flags y `totp_secret` reseteados |

### Reglas de negocio

1. Un `User` tiene exactamente un `UserProfile`.
2. **`company` es obligatorio** — no crear usuario sin compañía.
3. **UA solo crea usuarios tipo US** (no UA ni UF) y puede asignar cualquier compañía; **US** solo crea UF en su misma compañía.
4. Acceso a `/app/` requiere `is_security_complete = True` y suscripción vigente (excepto UA).
5. `status = "I"` o `locked_until` vigente bloquea el login.
6. Tras reset 2FA: limpiar códigos y flags de seguridad.
7. Sin `profile.company` → sin acceso a módulos de negocio (queryset vacío).

---

## Plan

**App:** `apps.billing`  
**Tabla:** `billing_plan`  
**Documento app:** [`billing.md`](billing.md)

Catálogo de planes contratables.

### Campos

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `id` | UUIDField | No | uuid4 | PK |
| `code` | SlugField(50) | No | — | Identificador único (`basic`, `pro`, `enterprise`) |
| `name` | CharField(100) | No | — | Nombre visible |
| `description` | TextField | Sí | `""` | Descripción |
| `billing_period` | CharField(20) | No | — | `monthly`, `annual`, `enterprise` |
| `price` | DecimalField(10,2) | Sí | — | Precio de referencia |
| `is_active` | BooleanField | No | `True` | Plan disponible |
| `created_at` | DateTimeField | No | auto_now_add | — |

**Relación inversa:** `plan.subscriptions` → conjunto de `Subscription`.

---

## Subscription

**App:** `apps.billing`  
**Tabla:** `billing_subscription`  
**Documento app:** [`billing.md`](billing.md)

Licencia de la compañía: vigencia, estado e integridad HMAC.

### Relaciones

| Campo | Tipo | Destino | `on_delete` | Acceso inverso |
|-------|------|---------|-------------|----------------|
| `company` | OneToOneField | `Company` | `CASCADE` | `company.subscription` |
| `plan` | ForeignKey | `Plan` | `PROTECT` | `plan.subscriptions` |
| `created_by` | ForeignKey | `User` | `SET_NULL` | `user.subscriptions_created` |
| `updated_by` | ForeignKey | `User` | `SET_NULL` | `user.subscriptions_updated` |

### Campos

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `id` | UUIDField | No | uuid4 | PK |
| `company` | OneToOneField → Company | No | — | Una suscripción por compañía |
| `plan` | ForeignKey → Plan | No | — | Plan contratado |
| `start_date` | DateField | No | — | Inicio de vigencia |
| `end_date` | DateField | No | — | Fin de vigencia |
| `status` | CharField(20) | No | `pending` | `active`, `expired`, `canceled`, `pending` |
| `auto_renew` | BooleanField | No | `False` | Renovación automática |
| `integrity_signature` | CharField(128) | Sí | — | HMAC-SHA256 sobre fechas |
| `created_at` | DateTimeField | No | auto_now_add | — |
| `updated_at` | DateTimeField | No | auto_now | — |

### Reglas

1. Máximo una `Subscription` por `Company`.
2. En `save()`: si `end_date` < hoy y `status == active` → `expired`.
3. Recalcular `integrity_signature` en cada `save()`; no usar `update()` sin recalcular.
4. `LICENSE_SECRET_KEY` obligatoria en producción.

---

## SubscriptionContact

**App:** `apps.billing`  
**Tabla:** `billing_subscriptioncontact`  
**Documento app:** [`billing.md`](billing.md)

Contactos de soporte de la suscripción (máx. 3).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUIDField | PK |
| `subscription` | FK → Subscription | `related_name="contacts"` |
| `name` | CharField(100) | Nombre |
| `email` | EmailField | Correo (único por suscripción si no null) |
| `phone` | CharField(50), null | Teléfono |
| `role` | CharField(50), null | Rol (soporte, facturación) |

Validación `clean()`: máximo 3 contactos por suscripción.

---

## Payment

**App:** `apps.billing`  
**Tabla:** `billing_payment`  
**Documento app:** [`billing.md`](billing.md)

Auditoría de cobros asociados a una suscripción.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUIDField | PK |
| `subscription` | FK → Subscription | `related_name="payments"` |
| `amount` | DecimalField(10,2) | Mín. 0.01 |
| `method` | CharField(20) | `manual`, `card`, `transfer`, `stripe`, `paypal` |
| `reference` | CharField(100), null | Referencia externa |
| `paid_at` | DateTimeField | Fecha del pago |
| `created_by` | FK → User, null | `user.payments_created` |

Validación: suscripción en `active` o `pending`.

---

## Project

**App:** `apps.projects`  
**Tabla:** `projects_project`  
**Documento app:** [`projects.md`](projects.md)

Contenedor de una tabla configurable dentro de una compañía: campos, registros y membresías.

### Relaciones

| Relación | Modelo | Cardinalidad | Notas |
|----------|--------|--------------|-------|
| `company` | `Company` | N:1 | **Obligatorio**, `on_delete=PROTECT`, `related_name="projects"` |
| `owner` | `auth.User` | N:1 | Creador (típicamente UF), `on_delete=PROTECT` |
| `memberships` | `ProjectMembership` | 1:N | Usuarios autorizados |
| `field_definitions` | `FieldDefinition` | 1:N | Esquema dinámico |
| `records` | `Record` | 1:N | Filas de datos |
| `expand_theme` | `ProjectRecordsExpandTheme` | 1:1 | Tema visual de `record_expand` (opcional) |

### Campos

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `id` | UUIDField | No | uuid4 | PK |
| `company` | ForeignKey → Company | No | — | Compañía dueña |
| `name` | CharField(200) | No | — | Nombre visible del proyecto |
| `slug` | SlugField(220) | No | — | Identificador URL; único por compañía |
| `description` | TextField | Sí | `""` | Descripción opcional |
| `owner` | ForeignKey → User | No | — | Usuario creador |
| `is_archived` | BooleanField | No | `False` | Oculto sin borrar datos |
| `project_kind` | CharField(20) | No | `workspace` | `workspace` \| `dms` — ver DMS |
| `created_at` | DateTimeField | No | auto_now_add | — |
| `updated_at` | DateTimeField | No | auto_now | — |

### Reglas de negocio

1. Al crear un proyecto, el `owner` recibe automáticamente `ProjectMembership` con rol `PA`.
2. `owner.profile.company` debe coincidir con `project.company`.
3. Par `(company, slug)` único.
4. Usuario solo ve proyectos de su compañía + membresía activa.
5. Proyecto archivado: solo lectura (configurable).

### Meta (Django)

```python
class Meta:
    unique_together = [("company", "slug")]
    ordering = ["-updated_at"]
    indexes = [
        models.Index(fields=["company", "slug"]),
        models.Index(fields=["company", "is_archived"]),
    ]
```

---

## ProjectRecordsExpandTheme

**App:** `apps.projects`  
**Tabla:** `projects_recordsexpandtheme`  
**Documento:** [`records_datatables_design.md`](records_datatables_design.md#modelo-django-propuesto)

Tema visual de la tabla expandida de registros (`record_expand.html`). **Un registro por proyecto**; el PA define colores y opciones. Sin registro → defaults técnicos del modelo.

### Relaciones

| Relación | Modelo | Cardinalidad | Notas |
|----------|--------|--------------|-------|
| `project` | `Project` | 1:1 | `on_delete=CASCADE`, `related_name="expand_theme"` |

### Campos (resumen)

| Grupo | Campos |
|-------|--------|
| Identidad | `id`, `project`, `created_at`, `updated_at` |
| Colores | `header_bg`, `header_color`, `header_border`, `cell_border`, `stripe_bg`, `hover_bg` |
| Clases DT | `grid_cell_border`, `layout_compact`, `row_stripe`, `row_hover`, `column_order_highlight`, `cell_nowrap` |
| Comportamiento | `page_length` (10–100) |

Sin campo `preset`. Definición completa y flujo al template: [`records_datatables_design.md`](records_datatables_design.md).

---

## ProjectMembership

**App:** `apps.projects`  
**Tabla:** `projects_projectmembership`  
**Documento app:** [`projects.md`](projects.md)

Vincula un usuario con un proyecto y su rol de acceso.

### Relaciones

| Relación | Modelo | Cardinalidad | Notas |
|----------|--------|--------------|-------|
| `project` | `Project` | N:1 | `on_delete=CASCADE` |
| `user` | `auth.User` | N:1 | `on_delete=CASCADE` |
| `invited_by` | `auth.User` | N:1 | Nullable, `on_delete=SET_NULL` |

### Campos

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `id` | UUIDField | No | uuid4 | PK |
| `project` | ForeignKey → Project | No | — | Proyecto |
| `user` | ForeignKey → User | No | — | Usuario miembro |
| `role` | CharField(2) | No | — | Rol en el proyecto |
| `invited_by` | ForeignKey → User | Sí | — | Quién otorgó el acceso |
| `is_active` | BooleanField | No | `True` | Membresía vigente |
| `created_at` | DateTimeField | No | auto_now_add | — |

**Valores permitidos (`role`):**

| Código | Nombre | Descripción |
|--------|--------|-------------|
| `PA` | Project Admin | Diseñar estructura, miembros, auditoría |
| `ED` | Editor | Crear y modificar registros |
| `CO` | Consulta | Solo lectura |
| `GE` | Generar | Exportar documentos |

### Reglas de negocio

1. Par `(project, user)` único.
2. El `user` invitado debe pertenecer a la **misma compañía** que el proyecto.
3. Sin membresía activa → sin acceso al proyecto.
4. Al menos un `PA` activo por proyecto.
5. Los tipos globales UA/US/UF **no sustituyen** el rol de proyecto.

### Meta (Django)

```python
class Meta:
    unique_together = [("project", "user")]
    indexes = [
        models.Index(fields=["project", "user", "is_active"]),
    ]
```

---

## FieldDefinition

**App:** `apps.fields`  
**Tabla:** `fields_fielddefinition`  
**Documento app:** [`fields.md`](fields.md)

Define una columna del esquema dinámico de un proyecto.

### Relaciones

| Relación | Modelo | Cardinalidad | Notas |
|----------|--------|--------------|-------|
| `project` | `Project` | N:1 | `on_delete=CASCADE` |
| `field_values` | `FieldValue` | 1:N | Valores en registros |

### Campos

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `id` | UUIDField | No | uuid4 | PK |
| `project` | ForeignKey → Project | No | — | Proyecto dueño |
| `key` | SlugField(100) | No | — | Identificador interno; único por proyecto |
| `label` | CharField(200) | No | — | Etiqueta visible en UI |
| `field_type` | CharField(30) | No | — | Tipo de dato (ver tabla) |
| `options` | JSONField | No | `{}` | Opciones: listas, min/max, decimales |
| `max_length` | PositiveIntegerField | Sí | — | Longitud máxima (texto) |
| `required` | BooleanField | No | `False` | Obligatorio al guardar registro |
| `sort_order` | PositiveIntegerField | No | `0` | Orden en listados y formularios |
| `version` | PositiveIntegerField | No | `1` | Versión del esquema |
| `is_active` | BooleanField | No | `True` | Campo visible/utilizable |
| `created_at` | DateTimeField | No | auto_now_add | — |
| `updated_at` | DateTimeField | No | auto_now | — |

**Valores permitidos (`field_type`) — MVP:**

| Código | Descripción | Columna principal en `FieldValue` |
|--------|-------------|-----------------------------------|
| `text_short` | Texto corto | `value_text` |
| `text_long` | Texto largo | `value_text` |
| `integer` | Entero | `value_number` |
| `decimal` | Decimal | `value_number` |
| `date` | Fecha | `value_date` |
| `datetime` | Fecha y hora | `value_json` o `value_text` ISO |
| `boolean` | Sí/No | `value_boolean` |
| `select` | Lista desplegable | `value_text` (opción en `options`) |

**Estructura sugerida de `options` (JSON):**

```json
{
  "choices": ["Pendiente", "En proceso", "Cerrado"],
  "min": 0,
  "max": 999999,
  "decimal_places": 2
}
```

### Reglas de negocio

1. Par `(project, key)` único.
2. Solo rol `PA` crea/edita/elimina campos.
3. Cambiar `field_type` incrementa `version` y requiere validación de datos existentes.
4. Campo inactivo (`is_active=False`) no aparece en formularios nuevos; datos históricos se conservan.

### Meta (Django)

```python
class Meta:
    unique_together = [("project", "key")]
    ordering = ["sort_order", "label"]
```

---

## Record

**App:** `apps.records`  
**Tabla:** `records_record`  
**Documento app:** [`records.md`](records.md)

Representa una fila de datos dentro de un proyecto (equivalente a una fila de Excel).

### Relaciones

| Relación | Modelo | Cardinalidad | Notas |
|----------|--------|--------------|-------|
| `project` | `Project` | N:1 | `on_delete=CASCADE` |
| `created_by` | `auth.User` | N:1 | `on_delete=PROTECT` |
| `updated_by` | `auth.User` | N:1 | Nullable, `on_delete=SET_NULL` |
| `field_values` | `FieldValue` | 1:N | Valores por campo |
| `history` | `RecordHistory` | 1:N | Auditoría |

### Campos

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `id` | UUIDField | No | uuid4 | PK |
| `project` | ForeignKey → Project | No | — | Proyecto |
| `created_by` | ForeignKey → User | No | — | Autor de creación |
| `updated_by` | ForeignKey → User | Sí | — | Última modificación |
| `created_at` | DateTimeField | No | auto_now_add | — |
| `updated_at` | DateTimeField | No | auto_now | — |
| `is_deleted` | BooleanField | No | `False` | Soft delete |

### Reglas de negocio

1. Todo `Record` pertenece a un único `Project`.
2. Al crear/actualizar se generan o actualizan `FieldValue` según `FieldDefinition` activos.
3. Soft delete: `is_deleted=True`; no aparece en listados por defecto.
4. Permisos: `edit` para crear/modificar; `view` para consulta.

### Meta (Django)

```python
class Meta:
    ordering = ["-updated_at"]
    indexes = [
        models.Index(fields=["project", "is_deleted", "-updated_at"]),
    ]
```

---

## FieldValue

**App:** `apps.records`  
**Tabla:** `records_fieldvalue`  
**Documento app:** [`records.md`](records.md)

Almacena el valor de un campo para un registro (modelo híbrido: columnas tipadas + JSON).

### Relaciones

| Relación | Modelo | Cardinalidad | Notas |
|----------|--------|--------------|-------|
| `record` | `Record` | N:1 | `on_delete=CASCADE` |
| `field` | `FieldDefinition` | N:1 | `on_delete=PROTECT` |

### Campos

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `id` | UUIDField | No | uuid4 | PK |
| `record` | ForeignKey → Record | No | — | Registro padre |
| `field` | ForeignKey → FieldDefinition | No | — | Definición del campo |
| `value_text` | TextField | Sí | — | Texto, select, email, URL |
| `value_number` | DecimalField(20,6) | Sí | — | Enteros y decimales |
| `value_date` | DateField | Sí | — | Fechas |
| `value_boolean` | BooleanField | Sí | — | Sí/No |
| `value_json` | JSONField | Sí | — | Tipos compuestos (multiselect, datetime) |
| `updated_at` | DateTimeField | No | auto_now | Última modificación del valor |

### Reglas de negocio

1. Par `(record, field)` único — un valor por campo por registro.
2. Solo una columna tipada activa según `field.field_type`; el resto en `null`.
3. Validación en servicio antes de persistir según `FieldDefinition`.
4. Índices en columnas tipadas para filtros eficientes en PostgreSQL.

### Meta (Django)

```python
class Meta:
    unique_together = [("record", "field")]
    indexes = [
        models.Index(fields=["field", "value_text"]),
        models.Index(fields=["field", "value_number"]),
        models.Index(fields=["field", "value_date"]),
        models.Index(fields=["field", "value_boolean"]),
    ]
```

---

## RecordHistory

**App:** `apps.audit`  
**Tabla:** `audit_recordhistory`  
**Documento app:** [`audit.md`](audit.md)

Trazabilidad de cambios: quién modificó qué y cuándo.

### Relaciones

| Relación | Modelo | Cardinalidad | Notas |
|----------|--------|--------------|-------|
| `record` | `Record` | N:1 | `on_delete=CASCADE` |
| `field` | `FieldDefinition` | N:1 | Nullable; null = acción sobre el registro |
| `user` | `auth.User` | N:1 | `on_delete=PROTECT` |

### Campos

| Campo | Tipo Django | Null | Default | Descripción |
|-------|-------------|------|---------|-------------|
| `id` | UUIDField | No | uuid4 | PK |
| `record` | ForeignKey → Record | No | — | Registro afectado |
| `field` | ForeignKey → FieldDefinition | Sí | — | Campo modificado (null = registro completo) |
| `user` | ForeignKey → User | No | — | Quién realizó el cambio |
| `action` | CharField(20) | No | — | Tipo de acción |
| `old_value` | TextField | Sí | — | Valor anterior (serializado) |
| `new_value` | TextField | Sí | — | Valor nuevo (serializado) |
| `created_at` | DateTimeField | No | auto_now_add | Momento del cambio |

**Valores permitidos (`action`):**

| Código | Descripción |
|--------|-------------|
| `create` | Registro creado |
| `update` | Campo o registro actualizado |
| `delete` | Soft delete del registro |
| `restore` | Restauración (fase posterior) |

### Reglas de negocio

1. Entradas **inmutables**: no editar ni eliminar historial.
2. Se escribe desde el servicio de `apps.records` al crear/actualizar/eliminar.
3. Solo rol `PA` (permiso `audit`) consulta historial completo por defecto.
4. `old_value` / `new_value` como texto serializado para independencia del tipo.

### Meta (Django)

```python
class Meta:
    ordering = ["-created_at"]
    indexes = [
        models.Index(fields=["record", "-created_at"]),
    ]
```

---

## Modelos DMS (`apps.dms`)

Extensión **Data Mapping Studio** — proyectos con `Project.project_kind = dms`. Documentación: [`../definition_app_DMS/dms_integration.md`](../definition_app_DMS/dms_integration.md).

| Modelo | Relación con plataforma | Descripción |
|--------|-------------------------|-------------|
| `DmsProjectConfig` | 1:1 `Project` | `visibility`, `current_version` |
| `DmsMappingVersion` | N:1 `Project` | Snapshot definición (origen, destino, mapeo); draft/published |
| `DmsSourceProfile` | 1:1 `DmsMappingVersion` | Definición origen — **asistente MVP en código** |
| `DmsTargetProfile` | 1:1 `DmsMappingVersion` | Definición destino — **asistente MVP en código** |
| `DmsFieldMapping` | N:1 `DmsMappingVersion` | Enlaces campo a campo (pendiente UI) |
| `DmsExecutionJob` | N:1 `Project` | Ejecución Fase C (pendiente) |
| `DmsSampleFile` | N:1 `Project` | Archivo muestra wizard (pendiente / file intake) |
| Catálogos (`SourceFileType`, …) | Globales | Ver `system_catalogs.md` — mantenimiento UA en código |

Los proyectos DMS **no** crean `FieldDefinition` ni `Record`.

---

## Resumen de integridad referencial

| Origen | Destino | on_delete | Motivo |
|--------|---------|-----------|--------|
| UserProfile → User | CASCADE | Borrar usuario elimina perfil |
| UserProfile → Company | PROTECT | No borrar compañía con usuarios |
| Subscription → Company | CASCADE | Suscripción ligada a compañía |
| Subscription → Plan | PROTECT | No borrar plan referenciado |
| Project → Company | PROTECT | No borrar compañía con proyectos |
| Project → User (owner) | PROTECT | No borrar usuario con proyectos |
| ProjectMembership → Project | CASCADE | Borrar proyecto elimina membresías |
| FieldDefinition → Project | CASCADE | Esquema ligado al proyecto |
| Record → Project | CASCADE | Datos ligados al proyecto |
| FieldValue → Record | CASCADE | Valores ligados al registro |
| FieldValue → FieldDefinition | PROTECT | No borrar campo con valores |
| RecordHistory → Record | CASCADE | Historial del registro |
| Record → User (created_by) | PROTECT | Preservar autor |
| Company → User (created_by) | SET_NULL | Preservar historial |

---

## Documentos relacionados

| Documento | Contenido |
|-----------|-----------|
| [`README.md`](README.md) | Índice de apps |
| [`CONVENCIONES.md`](CONVENCIONES.md) | Reglas transversales |
| [`../DynamicWorkspace.md`](../DynamicWorkspace.md) | Arquitectura y modelo híbrido |
| [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md) | Flujos de seguridad |
| [`company.md`](company.md) | App company |
| [`billing.md`](billing.md) | App billing |
| [`accounts.md`](accounts.md) | App accounts |
| [`projects.md`](projects.md) | App projects |
| [`fields.md`](fields.md) | App fields |
| [`records.md`](records.md) | App records |
| [`audit.md`](audit.md) | App audit |
| [`../definition_app_DMS/README.md`](../definition_app_DMS/README.md) | Data Mapping Studio |
| [`../definition_app_DMS/dms_integration.md`](../definition_app_DMS/dms_integration.md) | Integración DMS |
| [`../definition_app_DMS/source_definition.md`](../definition_app_DMS/source_definition.md) | SourceProfile / asistente origen |
| [`UI_MESSAGES.md`](UI_MESSAGES.md) | Mensajes UI (§3.8 DMS) |

---

## Mantenimiento

Al agregar o modificar un modelo:

1. Actualizar **este documento** (campos, relaciones, reglas).
2. Actualizar el documento de la app en `definition_app/<app>.md`.
3. Si afecta seguridad, actualizar [`../security/`](../security/).
4. Si cambia la arquitectura global, actualizar [`../DynamicWorkspace.md`](../DynamicWorkspace.md).

---

*Documento maestro de modelos — `docs/definition_app/DynamicWorkspace_Model.md`*
