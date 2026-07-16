# apps.projects



Proyectos configurables por compañía, membresías y permisos por proyecto.



---



## Propósito



Cada proyecto es una tabla independiente **dentro de una compañía**, con usuarios autorizados y roles propios.



---



## Responsabilidades



| Sí | No |

|----|-----|

| CRUD de `Project` (scoped por compañía) | Definición de campos (→ `apps.fields`) |

| `ProjectMembership` y roles | Valores de registros (→ `apps.records`) |

| Invitaciones a proyecto (misma compañía) | Autenticación (→ `apps.security`) |

| Verificación de permisos por rol | Compañía (→ `apps.company`) |



---



## Modelos



Detalle completo en [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md#project).



### Project



| Campo | Tipo | Descripción |

|-------|------|-------------|

| `id` | UUID | PK |

| `company` | FK Company | **Obligatorio** — compañía dueña |

| `name` | CharField | Nombre visible |

| `slug` | SlugField | URL amigable; único por compañía |

| `description` | TextField | Opcional |

| `owner` | FK User | Creador (UF); debe ser de la misma compañía |

| `is_archived` | BooleanField | Archivado |

| `created_at` / `updated_at` | DateTimeField | Auditoría |



### ProjectMembership



| Campo | Tipo | Descripción |

|-------|------|-------------|

| `project` | FK Project | — |

| `user` | FK User | Debe pertenecer a la misma compañía del proyecto |

| `role` | CharField(2) | PA / ED / CO / GE |

| `invited_by` | FK User, null | Quién invitó |

| `is_active` | BooleanField | Membresía activa |

| `created_at` | DateTimeField | — |



---



## Aislamiento por compañía



```python

def projects_for_user(user):

    company = user.profile.company

    return Project.objects.filter(company=company, ...)

```



- Listados filtrados por `profile.company`.

- Invitaciones solo a usuarios de la misma compañía.

- **UA** puede tener acceso cross-compañía para soporte (configurable).



---



## Roles por proyecto



| Rol | Código | Permisos principales |

|-----|--------|----------------------|

| Admin de proyecto | `PA` | Diseñar estructura, miembros, auditoría |

| Editor | `ED` | Crear y modificar registros |

| Consulta | `CO` | Solo lectura |

| Generar | `GE` | Exportar documentos |



El creador (UF) recibe `PA` automáticamente.



---



## Matriz de permisos



| Acción | PA | ED | CO | GE |

|--------|----|----|----|-----|

| Ver registros | Sí | Sí | Sí | Sí |

| Crear/editar registros | Sí | Sí | No | No |

| Diseñar campos | Sí | No | No | No |

| Gestionar miembros | Sí | No | No | No |

| Ver auditoría | Sí | No | No | No |

| Exportar | Sí | Sí | Sí | Sí |

| Importar Excel | Sí | Sí | No | No |



---



## Principio de acceso



1. Usuario con `profile.company` válida y suscripción vigente (US/UF).

2. Proyecto pertenece a la misma compañía.

3. Membresía activa en `ProjectMembership`.



---



## URLs previstas



| URL | Permiso | Descripción |

|-----|---------|-------------|

| `/app/proyectos/` | `view` | Listado de proyectos con membresía (UF) |
| `/app/proyectos/nuevo/` | UF (crear) | Crear proyecto en su compañía |

| `/app/proyectos/<slug>/` | `view` | Detalle / registros |

| `/app/proyectos/<slug>/miembros/` | `manage_members` | Gestionar usuarios |

| `/app/proyectos/<slug>/campos/` | `design` | Diseñador de campos |



---

## Prototipos HTML

Carpeta: `prototype/projects/` · Design system: **workbench ledger** (extiende `dashboard.css`).

| Prototipo | URL prevista | Layout | Descripción |
|-----------|--------------|--------|-------------|
| `project_list.html` | `/app/proyectos/` | Listado §10.8 | Listado UF con membresías (DataTables) |
| `project_create.html` | `/app/proyectos/nuevo/` | Formulario | Alta de proyecto (UF → PA automático) |
| `project_detail.html` | `/app/proyectos/<slug>/` | Detalle | Hub del workspace (registros, campos, miembros) |
| `project_members.html` | `/app/proyectos/<slug>/miembros/` | Listado §10.8 + form | Invitar y gestionar miembros (PA) |

### Layout (listados)

Alineado con [`VISTAS.md`](VISTAS.md#108-cobertura-de-pantalla-layout) §10.8 y referencia Django: `templates/company/company_list.html`, `templates/accounts/account_list.html`.

| Regla | Prototipo / producción |
|-------|------------------------|
| `app-main--wide` | Solo `project_list.html` y tabla de `project_members.html` |
| `panel panel--table` + `table-dt-host--projects` | Listados DataTables |
| Columna **Acciones** | `col-actions` + `actions actions--table` |
| Estado antes de fecha | Columnas «Estado» → «Actualizado» / «Desde» |
| Sin fila `{% empty %}` | Mensaje vacío en JS (`emptyTable`) |
| Formulario / detalle | `app-main` sin `--wide` (`project_create`, `project_detail`; formulario invitar en `project_members`) |

**Assets:** `projects.css`, `datatables-project.js`, `datatables-project-members.js` (reutiliza `../company/datatables-lang-es.js`).

**Sidebar UF:** Inicio + Proyectos (sin Cuentas ni Usuarios). Enlazado desde `prototype/dashboard/dashboard_uf_home.html`. Tarjeta **Campos** en `project_detail.html` → `prototype/fields/field_list.html`.

Tras el OK: migrar a `templates/projects/` extendiendo `app_base.html`; eliminar archivos de `prototype/projects/`.



---



## Dependencias



- `apps.company` — tenant

- `apps.accounts` — usuarios y perfiles

- `apps.core` — decoradores



## Fase



**Fase 1** — MVP.



## Documentos relacionados



- [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md)

- [`company.md`](company.md)

- [`accounts.md`](accounts.md)

- [`fields.md`](fields.md)

- [`../DynamicWorkspace.md`](../DynamicWorkspace.md)


