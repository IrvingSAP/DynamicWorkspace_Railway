# Módulo 1 — Ciclo de vida del proyecto (FILE CLEAN)

> **App:** File Clean · `project_kind=file_clean`  
> **Producto:** [`../FILE_CLEAN.md`](../FILE_CLEAN.md)  
> **Estado:** borrador de definición

---

## Objetivo

Permitir crear, listar, abrir el hub y gestionar miembros de un proyecto de limpieza, con el mismo patrón de chasis que Gate / Pipe / Match.

---

## Pantallas

| Pantalla | URL orientativa | Rol |
|----------|-----------------|-----|
| Listado | `/app/file-clean/proyectos/` | UF con membresía o visibilidad compañía |
| Nuevo | `/app/file-clean/proyectos/nuevo/` | UF |
| Hub | `/app/file-clean/proyectos/<slug>/` | Miembros |
| Miembros | `/app/file-clean/proyectos/<slug>/miembros/` | PA |
| Ayudas | `…/ayuda/` | Según pantalla |

---

## Datos al crear

| Campo | Reglas |
|-------|--------|
| Nombre | Obligatorio |
| Slug | Único por compañía; minúsculas |
| Descripción | Opcional |
| Visibilidad | `members_only` \| `company` (reuso DmsProjectConfig / equivalente) |

Al crear: owner = PA; `CleanConfig` vacío; sin versión publicada.

---

## Hub — módulos visibles

1. Perfil de lectura  
2. Reglas de limpieza  
3. Publicar  
4. Ejecutar  
5. Historial  

Indicadores: ¿hay borrador?, ¿hay versión publicada?, último job.

---

## Reglas

- Solo UF crea proyectos.  
- Soft archive alineado a otros kinds.  
- Sin membresía activa → no aparece en listados personales.

---

## API-ready

No hay endpoint de “crear proyecto” en MVP API. El diseño de listado/hub no bloquea `kind=file_clean` en ejecución remota posterior.

---

## Criterio de aceptación del módulo

- [x] CRUD listado/alta/hub coherente con sidebar Title Case **File Clean**  
- [x] Roles PA en alta  
- [x] Mensajes según UI_MESSAGES  
- [x] Spec lista para prototipo `prototype/file_clean/projects_*.html`  
- [x] Revisión UX de prototipos OK → «Desarrolla el módulo» (M1 implementado)
