# apps.accounts



Gestión de usuarios, perfiles y alta administrada (UA/US). Cada usuario pertenece a una **compañía**.



---



## Propósito



Mantener `UserProfile` con compañía obligatoria, tipo de usuario global (UA/US/UF) y exponer vistas de administración de cuentas.



---



## Responsabilidades



| Sí | No |

|----|-----|

| Modelo `UserProfile` con FK `company` | Wizard de login (→ `apps.security`) |

| Alta de usuarios por UA/US (con compañía) | CRUD de compañías (→ `apps.company`) |

| Signal `post_save` → crear perfil | Suscripción (→ `apps.billing`) |

| Vista listado/creación usuarios | Permisos por proyecto (→ `apps.projects`) |
| Definición de aprovisionamiento masivo UF (CSV) — [`accounts_provisioning.md`](accounts_provisioning.md), **pendiente** Fase 1+ | — |



---



## Modelos



Detalle completo en [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md#userprofile).



### User (django.contrib.auth)



| Campo | Uso |

|-------|-----|

| `username` | Login |

| `email` | Verificación y notificaciones (Resend) |

| `password` | Hash Django |

| `is_active` | Desactivación global |



### UserProfile



OneToOne con `User`. **ForeignKey obligatorio** a `Company`.



#### Compañía (tenant)



| Campo | Tipo | Uso |

|-------|------|-----|

| `company` | FK → Company | **Obligatorio** — compañía del usuario |



Patrón de acceso (como CODAS `apps.userprofile`):



```

request.user → user.profile → profile.company

```



#### Tipo de usuario global



| Código | Nombre | Descripción |

|--------|--------|-------------|

| `UA` | User Admin | Administrador del sistema |

| `US` | User System | Crea usuarios UF en su compañía |

| `UF` | User Final | Crea proyectos; autoriza miembros |



#### Campos principales



| Campo | Tipo | Default | Uso |

|-------|------|---------|-----|

| `company` | FK Company | — | **Obligatorio** |

| `user_type` | CharField(2) | `'UF'` | UA / US / UF |

| `email_confirmed` | BooleanField | `False` | Correo verificado |

| `email_confirm_code` | CharField(6), null | — | Código enviado |

| `email_confirm_exp` | DateTimeField, null | — | Caducidad +5 min |

| `totp_secret` | CharField(64), null | — | Secreto pyotp |

| `tfa_verified` | BooleanField | `False` | TOTP verificado |

| `last_totp_reset` | DateTimeField, null | — | Auditoría |

| `status` | CharField(1) | `'A'` | A=activo, I=inactivo |

| `locked_until` | DateTimeField, null | — | Bloqueo temporal |

| `primer_acceso_completado` | BooleanField | `False` | Visitó bienvenida |

| `created_by` / `updated_by` | FK User, null | — | Auditoría |

| `created_at` / `updated_at` | DateTimeField | auto | Auditoría |



#### Propiedades



```python

@property

def is_security_complete(self):

    return self.email_confirmed and self.tfa_verified and bool(self.totp_secret)



@property

def can_create_users(self):

    return self.user_type in ("UA", "US")



@property

def can_access_app(self):

    # UA exento de suscripción; US/UF requieren company.subscription vigente

    ...

```



---



## Matriz de permisos globales



| Acción | UA | US | UF |

|--------|----|----|-----|

| Crear compañías | Sí | No | No |

| Crear usuarios UA | No | No | No |

| Crear usuarios US | Sí | No | No |

| Crear usuarios UF | No | Sí (misma compañía) | No |

| Crear proyectos | Configurable | Configurable | Sí (su compañía) |



---



## URLs previstas

| URL | Vista | Acceso | Alcance del listado / CRUD |
|-----|-------|--------|----------------------------|
| `/app/admin/usuarios/` | `account_list` | UA, US | UA → solo **US** (todas las compañías). US → solo **UF** de `profile.company` |
| `/app/admin/usuarios/nuevo/` | `account_create` | UA, US | UA crea **US** (elige compañía). US crea **UF** (compañía fija) |
| `/app/admin/usuarios/<id>/` | `account_detail` | UA, US | Solo si el usuario objetivo está en el alcance del actor |
| `/app/admin/usuarios/<id>/editar/` | `account_update` | UA, US | Idem |
| `/app/admin/usuarios/<id>/eliminar/` | `account_confirm_delete` | UA, US | Idem |

> **UF** no accede a estas URLs. Menú lateral: ítem «Usuarios» → `/app/admin/usuarios/` (UA y US). «Cuentas» en UA apunta a compañías (`apps.company`); ver [`dashboard.md`](dashboard.md).

---

## List y CRUD — alcance por rol (UA vs US)

### Reglas de negocio (resumen)

| Actor | Ve en listado | Puede crear | Compañía en alta |
|-------|---------------|-------------|------------------|
| **UA** | Usuarios tipo **US** | Solo **US** | Selector (cualquier compañía activa) |
| **US** | Usuarios tipo **UF** de su compañía | Solo **UF** | Fija (`request.user.profile.company`), sin selector |
| **UF** | — | — | Sin acceso al módulo |

La seguridad **no** depende del HTML: el servicio filtra querysets, fija `user_type` y `company` en POST, y la vista valida que `<id>` pertenezca al alcance.

### Decisión de diseño: ¿HTML separados o un solo template?

**Recomendado para Django (producción):** **una vista + un template por acción**, con **contexto según el actor** — no duplicar el CRUD completo por rol.

| Enfoque | Veredicto |
|---------|-----------|
| `account_list_ua.html` + `account_list_us.html` (CRUD duplicado) | ❌ Evitar — doble mantenimiento, riesgo de divergencia |
| Un solo `account_list.html` + `{% if management_scope.target_type %}` en todo | ⚠️ Aceptable si hay pocos condicionales |
| Un template + **includes** por rol + **mismo servicio** | ✅ **Preferido** |

**Patrón acordado:**

```
Vista account_list (una)
  → servicio list_manageable_users(actor_profile)
  → contexto management_scope
  → render "accounts/account_list.html"

account_list.html
  → columnas y textos según management_scope
  → {% include "includes/account_toolbar.html" %}
  → formulario create: {% include "includes/account_form_fields.html" %}
```

### Objeto `management_scope` (contexto)

La vista siempre pasa un dict (o dataclass) derivado del usuario conectado:

| Clave | UA | US |
|-------|----|----|
| `actor_type` | `UA` | `US` |
| `target_type` | `US` | `UF` |
| `page_eyebrow` | «Administradores de compañía» | «Usuarios finales» |
| `list_title` | «Usuarios US» | «Usuarios UF» |
| `show_company_column` | `True` | `False` (siempre la misma compañía) |
| `show_company_picker` | `True` (create/update) | `False` |
| `fixed_company` | `None` | `request.user.profile.company` |
| `allowed_user_types` | `["US"]` | `["UF"]` |
| `stats_label` | p. ej. US activos / inactivos | p. ej. UF activos / inactivos |

El campo `user_type` en create **no** se muestra como libre elección: va **oculto** o **solo lectura** con el valor de `target_type`.

### Servicios (`apps/accounts/services/`)

| Función | Responsabilidad |
|---------|-----------------|
| `get_management_scope(actor_profile)` | Devuelve `management_scope` según UA/US |
| `list_manageable_users(actor)` | Queryset: `user_type=target_type`, US además `company=actor.company` |
| `get_manageable_user(actor, pk)` | `get_object_or_404` con filtro de alcance |
| `create_from_post(actor, POST)` | Fuerza `user_type` y `company`; valida reglas § matriz |
| `update_from_post(actor, user, POST)` | No permitir cambiar `user_type` ni `company` fuera de alcance |
| `delete_user(actor, user)` | Mismas comprobaciones + reglas de negocio |

### Prototipos HTML (`prototype/accounts/`)

| Archivo | Simula | Producción Django |
|---------|--------|-------------------|
| `account_list_ua.html` | UA → listado **US** (columna compañía) | `account_list.html` + `management_scope` UA |
| `account_list_us.html` | US → listado **UF** (compañía fija ACME) | `account_list.html` + `management_scope` US |
| `account_create.html` | Alta unificada (toggle UA/US) | `account_create.html` |
| `account_detail.html` | Detalle unificada (toggle) | `account_detail.html` |
| `account_update.html` | Edición unificada (toggle) | `account_update.html` |
| `account_confirm_delete.html` | Borrado unificada (toggle) | `account_confirm_delete.html` |

**Assets:** `accounts.css`, `prototype-scope.js` (solo prototipo), `datatables-account-ua.js`, `datatables-account-us.js`.

Tras el OK: un solo `account_list.html` en `templates/accounts/`; eliminar `account_list_ua.html` y `account_list_us.html` del prototipo.

### Decoradores

```python
@login_required
@security_complete_required
@user_type_required("UA", "US")
def account_list(request):
    scope = account_service.get_management_scope(request.user.profile)
    users = account_service.list_manageable_users(request.user.profile)
    return render(request, "accounts/account_list.html", {
        "users": users,
        "management_scope": scope,
        "app_nav_active": "accounts",
    })
```

### Mensajes UI

Al implementar: [`UI_MESSAGES.md`](UI_MESSAGES.md) §3.4 y §3.7 (textos específicos: «Usuario US creado», «Solo puede crear usuarios UF», etc.).

---



## Reglas



- Signal `post_save` en `User` crea `UserProfile` — la compañía se asigna en el formulario de alta.

- **Todo usuario creado debe tener `company`**; no permitir perfil sin compañía.

- **UA solo puede crear usuarios tipo US** (no UA ni UF); asigna compañía libremente.

- US solo crea UF en su propia compañía.

- Sin `profile.company` → sin acceso a módulos de negocio.

- Flujos de seguridad: ver [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md).

- Licencia: ver [`company.md`](company.md) y [`billing.md`](billing.md).



---



## Dependencias



- `apps.company` — `Company`

- `apps.billing` — validación de suscripción

- `apps.core` — decoradores, correo



## Fase

**Fase 0** — CRUD manual, perfiles, integración con security.

**Fase 1+** — Aprovisionamiento masivo UF: ver [`accounts_provisioning.md`](accounts_provisioning.md) (**pendiente**, no bloquea Fase 0).

---

## Tareas de implementación

### Fase 0 (prioritaria — otras apps no dependen del batch)

- [ ] Modelos `User` / `UserProfile` y signal `post_save`
- [ ] Servicios CRUD con `management_scope` (UA→US, US→UF)
- [ ] Vistas y templates: `account_list`, `account_create`, `account_detail`, `account_update`, `account_confirm_delete`
- [ ] Prototipos OK → migrar a `templates/accounts/` (list dual en prototipo → unificado en Django)
- [ ] Mensajes [`UI_MESSAGES.md`](UI_MESSAGES.md) §3.7
- [ ] Integración menú dashboard (Usuarios → `/app/admin/usuarios/`)

### Pendiente — aprovisionamiento masivo (Fase 1+)

Documento: [`accounts_provisioning.md`](accounts_provisioning.md)

- [ ] Modelos `ProvisioningJob` / `ProvisioningJobRow`
- [ ] CSV v1 CREATE y DEACTIVATE + plantillas descargables
- [ ] Validaciones por fila y pre-scan duplicados en archivo
- [ ] Contraseña temporal (fórmula) + onboarding diferido
- [ ] UI importar + mantenimiento de jobs
- [ ] Worker asíncrono e informe de errores exportable
- [ ] Integración externa (carpeta/API) — Fase 2

---

## Documentos relacionados

- [`accounts_provisioning.md`](accounts_provisioning.md) — carga masiva UF (**pendiente** Fase 1+)

- [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md)

- [`company.md`](company.md)

- [`billing.md`](billing.md)

- [`UI_MESSAGES.md`](UI_MESSAGES.md) — permisos §3.4; añadir §3.7 al implementar CRUD usuarios

- [`security.md`](security.md)

- [`projects.md`](projects.md)

- [`../security/SEGURIDAD_Y_ACCESOS.md`](../security/SEGURIDAD_Y_ACCESOS.md)


