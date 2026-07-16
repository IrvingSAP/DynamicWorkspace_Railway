# apps.dashboard

Zona privada autenticada: home, bienvenida y navegación principal. El dashboard varía según el **tipo de usuario** (`UserProfile.user_type`).

---

## Propósito

Punto de entrada tras login exitoso. Presenta un resumen operativo acorde al rol del usuario autenticado.

| Código | Rol | Dashboard |
|--------|-----|-----------|
| UA | User Admin | Vista global de plataforma (todas las compañías) |
| US | User System | Vista de su compañía (usuarios UF, licencia) |
| UF | User Final | Vista de proyectos y membresías propias |

Referencia de tipos: [`accounts.md`](accounts.md).

---

## Responsabilidades

| Sí | No |
|----|-----|
| Home `/app/` según tipo de usuario | CRUD de entidades (→ apps correspondientes) |
| Bienvenida primer acceso `/app/bienvenida/` | Login (→ `apps.security`) |
| Layout base de la zona privada | Diseño de campos |
| KPIs y resúmenes de lectura | Edición inline de datos |

---

## URLs previstas

| URL | Vista | Descripción |
|-----|-------|-------------|
| `/app/` | `dashboard:home` | Dashboard según `user_type` (UA / US / UF) |
| `/app/bienvenida/` | `dashboard:bienvenida` | Primer acceso post-onboarding |

---

## Menú lateral por tipo de usuario

### UA — User Admin

| Ítem | Destino | Notas |
|------|---------|-------|
| Inicio | `/app/` | Activo en home |
| Compañías | `/app/admin/compañias/` | Listado y administración de tenants |
| Cuentas | `/app/accounts/` | Gestión global de cuentas |
| Usuarios | *(ruta pendiente)* | Alta y gestión de usuarios US |
| Cerrar sesión | logout | — |
| Usuario | — | `auth_user.username` en pie del menú |

> UA gestiona compañías desde el menú lateral; billing sigue como acceso rápido en el dashboard.

### US — User System

| Ítem | Destino | Notas |
|------|---------|-------|
| Inicio | `/app/` | Activo en home |
| Compañía | `/app/admin/compañias/<id>/` | Solo lectura de su tenant (`profile.company`) |
| Cuentas | `/app/accounts/` | Solo UF de su compañía |
| Usuarios | *(ruta pendiente)* | Alta y gestión de usuarios UF |
| Cerrar sesión | logout | — |
| Usuario | — | `auth_user.username` en pie del menú |

> **US solo crea usuarios UF** en su compañía (`profile.company`). Todos los datos del dashboard se filtran por esa compañía.

### UF — User Final

| Ítem | Destino | Notas |
|------|---------|-------|
| Inicio | `/app/` | Activo en home |
| Proyectos | `/app/proyectos/` | Listado de proyectos con membresía activa |
| Ayuda | `/app/ayuda/` | Guía general de flujos de trabajo (no ayuda campo a campo) |
| Cerrar sesión | logout | — |
| Usuario | — | `auth_user.username` en pie del menú |

> **UF no ve** Cuentas, Usuarios ni billing. Su ámbito es personal: proyectos donde tiene `ProjectMembership` activa en su compañía. Solo UF crea proyectos y, como **PA**, autoriza miembros.

**Menú descartado (y por qué):**

| Ítem | Motivo |
|------|--------|
| Cuentas / Usuarios | Gestión de cuentas es UA/US; UF autoriza por proyecto, no crea usuarios |
| Billing / Licencias | Solo lectura operativa; la licencia la gestiona US/UA |
| Campos / Registros | Acceso contextual dentro de cada proyecto (`/app/proyectos/<slug>/`) |
| Miembros (global) | Gestionar miembros es por proyecto (`…/miembros/`), no en menú raíz |

---

## Dashboard UA — especificación

**Prototipo:** `prototype/dashboard/dashboard_ua_home.html`

**Intento de diseño (interface-design):** operador de plataforma que revisa salud global al iniciar sesión — compañías, usuarios, licencias y alertas de vencimiento.

### KPIs principales (fila superior)

| Métrica | Fuente modelo | Alcance |
|---------|---------------|---------|
| Compañías | `Company` | Total, activas / inactivas (`is_active`) |
| Usuarios | `UserProfile` + `User` | Total, activos / inactivos |
| Proyectos | `Project` | Total en todas las compañías |
| Suscripciones activas | `Subscription` | `status = active` |

### Widgets secundarios

| Widget | Datos | Modelo / campo |
|--------|-------|----------------|
| Usuarios por tipo | Conteo UA / US / UF | `UserProfile.user_type` |
| Estado de seguridad | Correo pendiente, 2FA pendiente, bloqueados | `email_confirmed`, `tfa_verified`, `User.is_active` |
| Licencias y billing | Plan más usado, ingresos del mes, próximo vencimiento, último pago | `Plan`, `Payment`, `Subscription` |
| Estado de suscripciones | Activas, vencidas, pendientes | `Subscription.status` |
| Por vencer (30 días) | Tabla compañía · plan · fecha | `Subscription.end_date` |
| Actividad reciente | Últimos eventos de plataforma | Alta compañía, usuario, pago, proyecto |

### Accesos rápidos (cuerpo)

Enlaces a módulos que UA gestiona pero no están en el menú lateral:

- Compañías → `company:company_list`
- Cuentas → `accounts:…`
- Planes y suscripciones → `billing:…`
- Pagos → `billing:payment_list`

### Datos adicionales evaluados (modelo)

Según [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md), otros datos útiles para UA en iteraciones futuras:

| Dato | Modelo | Prioridad |
|------|--------|-----------|
| Distribución por plan (Basic / Pro / Enterprise) | `Plan` + `Subscription` | Media — parcial en widget billing |
| Contactos de suscripción | `SubscriptionContact` | Baja — detalle en billing |
| Registros totales | `Record` | Baja — Fase 1, métrica de adopción |
| Proyectos por compañía | `Project` | Media — posible tabla ranking |
| Usuarios sin compañía activa | `UserProfile` + `Company.is_active` | Media — alerta |

---

## Dashboard US — especificación

**Prototipo:** `prototype/dashboard/dashboard_us_home.html`

**Intento de diseño (interface-design):** administrador de compañía que revisa usuarios UF, proyectos y vigencia de licencia al iniciar sesión — vista acotada a `profile.company`.

### Diferencias respecto a UA

| Aspecto | UA | US |
|---------|----|----|
| Alcance de datos | Global (todas las compañías) | Solo `profile.company` |
| KPI «Compañías» | Total plataforma | Nombre y estado de **su** compañía |
| Usuarios por tipo | UA / US / UF | US + UF de la compañía (sin UA) |
| Crear usuarios | Solo US | Solo UF |
| Billing — ingresos | Muestra «Ingresos del mes» | **No** muestra ingresos |
| Suscripciones | Múltiples compañías | Una licencia (la de su compañía) |
| Accesos rápidos | Compañías, billing global, pagos | Cuentas, usuarios UF, licencia |

### KPIs principales (fila superior)

| Métrica | Fuente modelo | Alcance |
|---------|---------------|---------|
| Compañía | `Company` | `profile.company` — nombre, `is_active`, plan |
| Usuarios | `UserProfile` | Filtrado por `company_id`; desglose US / UF |
| Proyectos | `Project` | `company_id = profile.company` |
| Licencia | `Subscription` | Suscripción de su compañía — estado y vencimiento |

### Widgets secundarios

| Widget | Datos | Notas |
|--------|-------|-------|
| Usuarios de la compañía | US + UF, estado seguridad | Botón «Crear UF» |
| Licencias y billing | Plan, vencimiento, último pago (fecha) | Sin ingresos ni montos agregados |
| Vencimiento de licencia | Plan · inicio · fin · estado | Una fila |
| Actividad reciente | Eventos en la compañía | Sin columna compañía |

### Accesos rápidos

- Cuentas → `accounts:…` (UF de su compañía)
- Usuarios UF → alta/gestión UF
- Licencia → vista de solo lectura de su suscripción

---

## Dashboard UF — especificación

**Prototipo:** `prototype/dashboard/dashboard_uf_home.html`

**Intento de diseño (interface-design):** operador que reemplaza Excel — al entrar necesita retomar sus tablas, ver dónde es admin y autorizar colegas. El dashboard actúa como **lanzador de workspace**, no como panel administrativo.

### Alcance de datos

Todo filtrado por:

1. `profile.company` — misma compañía del usuario
2. `ProjectMembership.is_active = True` — solo proyectos donde tiene acceso
3. Métricas personales — no datos globales ni de otros usuarios fuera de sus proyectos PA

### Diferencias respecto a UA y US

| Aspecto | UA | US | UF |
|---------|----|----|-----|
| Alcance | Plataforma | Compañía | Proyectos con membresía |
| Menú | Inicio, Cuentas, Usuarios | Inicio, Cuentas, Usuarios | Inicio, Proyectos, Ayuda |
| Crear usuarios | Solo US | Solo UF | No |
| Crear proyectos | No (configurable) | No (configurable) | **Sí** |
| Autorizar miembros | No | No | **Sí** (rol PA) |
| Billing | Completo + ingresos | Sin ingresos | **No visible** |

### KPIs principales (fila superior)

| Métrica | Fuente modelo | Alcance |
|---------|---------------|---------|
| Mis proyectos | `Project` + `ProjectMembership` | Membresías activas del usuario; activos vs archivados |
| Registros | `Record` | Total en proyectos accesibles (Fase 1) |
| Como admin (PA) | `ProjectMembership.role` | Proyectos donde es PA y puede gestionar miembros/campos |

### Widgets secundarios

| Widget | Datos | Modelo / campo |
|--------|-------|----------------|
| Proyectos recientes | Nombre, rol, registros, `updated_at` | `Project`, `ProjectMembership`, `Record` |
| Mis roles por proyecto | Conteo PA / ED / CO / GE | `ProjectMembership.role` |
| Autorizaciones recientes | Proyecto · usuario · rol · fecha | `ProjectMembership` (PA del usuario) |
| Actividad reciente | Registro creado/editado, miembro autorizado, proyecto creado | `Record`, `RecordHistory`, `Project` |

### Accesos rápidos

- Crear proyecto → `/app/proyectos/nuevo/` (solo UF)
- Ver todos los proyectos → listado
- Acceso directo a proyectos frecuentes (últimos 2–3)

### Reglas de negocio aplicadas

- UF **crea proyectos** en su compañía; al crear recibe rol **PA** automáticamente ([`projects.md`](projects.md)).
- UF **autoriza miembros** solo en proyectos donde es PA; invitaciones limitadas a usuarios de la misma compañía.
- Sin membresía activa → el proyecto no aparece en el dashboard.
- Proyecto archivado → visible con indicador; solo lectura (configurable).
- Requiere suscripción vigente de la compañía para acceder a `/app/` ([`DynamicWorkspace.md`](../DynamicWorkspace.md)).

### Datos evaluados para iteraciones futuras

| Dato | Modelo | Prioridad |
|------|--------|-----------|
| Campos por proyecto | `FieldDefinition` | Media — en detalle de proyecto |
| Importaciones pendientes | `ImportJob` | Baja — Fase 2 |
| Auditoría reciente | `RecordHistory` | Media — widget actividad |
| Exportaciones recientes | — | Baja — rol GE |
| Invitaciones pendientes (`is_active=False`) | `ProjectMembership` | Media — alerta en dashboard |

### Ayuda general UF

**Implementado:** `templates/help/uf_guide.html` · **URL:** `/app/ayuda/` (`help:uf_guide`)

Detalle en [`help.md`](help.md). Prototipo origen: `prototype/help/uf_guide.html`.

Guía de **flujos de trabajo** (no catálogo de campos por pantalla). Complementa la ayuda contextual (`?` en formularios y listados).

| Flujo | Para qué sirve | Roles |
|-------|----------------|-------|
| Inicio y panel | Orientación diaria, proyectos recientes | Todos |
| Crear proyecto | Nueva tabla / proceso | PA |
| Diseñar campos | Esquema de columnas | PA |
| Autorizar equipo | Membresías y permisos | PA |
| Gestionar registros | CRUD de filas | PA, ED, CO |
| Vista expandida | Tabla a pantalla completa + apariencia | Todos / PA config |
| Consulta y exportación | Solo lectura y salidas | CO, GE, PA |

---

## Reglas

- Todas las vistas con `security_complete_required`
- Primer acceso: `primer_acceso_completado = False` → redirect a bienvenida
- Plantilla base `app_base.html` para herencia en otras apps
- **UA** ve datos globales (sin filtro de compañía)
- **US** y **UF** filtran por `profile.company` y permisos de membresía

---

## Dependencias

- `apps.security` — autenticación completa
- `apps.accounts` — tipos de usuario, perfiles
- `apps.company` — compañías (UA)
- `apps.billing` — planes, suscripciones, pagos (UA, US)
- `apps.projects` — proyectos (UA global, UF personal)

## Fase

**Fase 0** (UA, US home) · **Fase 1** (métricas de proyectos/registros en UF).

## Documentos relacionados

- [`accounts.md`](accounts.md)
- [`billing.md`](billing.md)
- [`company.md`](company.md)
- [`projects.md`](projects.md)
- [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md)
- [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md)
- Prototipo UA: [`../../prototype/dashboard/dashboard_ua_home.html`](../../prototype/dashboard/dashboard_ua_home.html)
- Prototipo US: [`../../prototype/dashboard/dashboard_us_home.html`](../../prototype/dashboard/dashboard_us_home.html)
- Prototipo UF: [`../../prototype/dashboard/dashboard_uf_home.html`](../../prototype/dashboard/dashboard_uf_home.html)
- Ayuda UF (flujos): [`help.md`](help.md) · plantilla [`../../templates/help/uf_guide.html`](../../templates/help/uf_guide.html)
