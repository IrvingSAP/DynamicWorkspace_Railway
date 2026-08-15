# Futura mejora — Estado de proyecto (`en_proceso` / `activo` / `inactivo`)

> **Estado:** documentado, **no implementado**.  
> **Alcance:** campo común en `apps.projects.Project` (todos los `project_kind`) + listados principales de todas las apps + consumidores (p. ej. Pepeline).  
> **Origen:** análisis FilePipe / listado Data Mapping (agosto 2026). No generar código hasta que se priorice.

---

## Problema

Con muchos proyectos el usuario necesita:

- Filtrar los que puede usar.
- **Inactivar** uno sin borrarlo (deja de entrar en orquestación, p. ej. **Pepeline**).
- Distinguir los que aún no cerraron el ciclo de definición.

Hoy `Project.is_archived` cubre un soft-archive (índice `company + is_archived`). El KPI «Activos» de varios listados lo usa, pero **FilePipe y la mayoría de apps de archivo no exponen** filtro ni acción Inactivar/Reactivar. El avance «en proceso» vive en el stepper del hub, no como estado persistido del proyecto.

Un enum nuevo de tres valores **no es caro en BD**; lo caro es el **contrato de transiciones** y unificar **todas las listas y pickers**.

---

## Estados propuestos

| Valor | Quién lo decide | Significado |
|-------|-----------------|-------------|
| `en_proceso` | Sistema | El usuario está creando / no ha culminado el ciclo de esa app. |
| `activo` | Sistema | Cumplió el ciclo; Pepeline y pickers pueden tomarlo. |
| `inactivo` | Usuario (PA) | Baja explícita. **No** entra en Pepeline aunque el ciclo esté cerrado. |

Pepeline (y selectores equivalentes): **solo `activo`**.

---

## Campo (cuando se implemente)

- Modelo: `apps.projects.Project` (tabla `projects_project`).
- Tipo sugerido: `CharField` con choices `en_proceso` / `activo` / `inactivo`, default `en_proceso`.
- Índice sugerido: `(company, estado)` y/o `(company, project_kind, estado)`.
- Relación con `is_archived`: **una sola palanca de baja**. O `inactivo` sustituye el archivo en UX, o se mapea `inactivo` ↔ `is_archived`. Dos bajas (archivado e inactivo) confunden listados y a Pepeline.

**No** persistir «en proceso» como edición manual del avance del hub: se desincroniza.

---

## Transiciones

1. **Alta** → `en_proceso`.
2. **Al publicar / completar el ciclo de ese `project_kind`** → `activo` **solo si no está `inactivo`**.
3. **Inactivar** (PA, confirmación) → `inactivo`; permanece aunque editen o vuelvan a publicar.
4. **Reactivar** → `activo` si el ciclo sigue cerrado; si no, `en_proceso`.
5. **Editar un activo:** no bajar a `en_proceso` al tocar el borrador. Pepeline debe seguir usando la **versión publicada**.

El campo es **común**; la regla «ciclo cumplido» es **por kind**:

| App | Criterio razonable (hoy) |
|-----|--------------------------|
| FilePipe (`dms`) | Origen + destino + mapeo + reglas **y versión publicada** |
| FILE GATE | Contrato (+ políticas) **publicado** |
| FILE CLEAN / Split-Merge / FILE MATCH / Reverse | Definición **publicada** según su hub |
| STRUCTURE SCOUT | Exploración aplicable (p. ej. borrador listo / apply); no es publicar ETL |
| Workspace | No hay ese ciclo; definir criterio propio o «activo» al crear |

Servicio sugerido: `is_cycle_complete(project)` por kind; no un `if` genérico. Publicar/completar actualiza el campo; inactivar/reactivar es lo único 100 % manual.

---

## Impacto de pantallas

Todas las **listas principales** (FilePipe, FILE GATE, Clean, Match, Scout, Reverse, Split/Merge, Workspace):

- Columna **Estado** + filtro (por defecto Activo; En proceso / Inactivo / Todos).
- KPI: no mezclar «Activos» = `not is_archived` con `estado=activo`.
- Acciones PA: Inactivar / Reactivar + mensajes en [`UI_MESSAGES.md`](UI_MESSAGES.md).
- Ayudas de cada listado.

**Pickers:** seed / importar estructura, bridge FILE GATE, destinos Scout, **Pepeline** → solo `activo`.

**Ejecutar / validar / generar:** proyecto `inactivo` no corre (o bloqueo duro).

Si Pepeline cachea slugs, inactivar debe notarse al armar o al ejecutar el job.

---

## Backfill (proyectos existentes)

Sugerencia:

- `is_archived=True` → `inactivo`.
- Ciclo cerrado (p. ej. versión publicada) → `activo`.
- Resto → `en_proceso`.

---

## Orden de implementación (cuando se priorice)

1. Modelo + migración + backfill + índice.  
2. Reglas por kind al publicar / completar ciclo.  
3. Inactivar / Reactivar (PA) + bloqueos.  
4. Columna y filtro en **todas** las listas principales.  
5. Pepeline y demás pickers.  
6. Mensajes UI y ayudas.

---

## Fuera de alcance de esta mejora

- Recalcular «en proceso» en cada paso del wizard (ruido; basta publicar/completar).
- Un `estado` distinto por app (rompe Pepeline y el listado transversal).
- Borrado físico de proyectos.

---

## Relacionado

- [`projects.md`](projects.md) — `Project.is_archived` actual  
- [`DynamicWorkspace_Model.md`](DynamicWorkspace_Model.md#project) — modelo compartido  
- [`../definition_app_DMS/project_lifecycle.md`](../definition_app_DMS/project_lifecycle.md) — ciclo FilePipe  
- [`../APP_FACTORY_FILE_OPS.md`](../APP_FACTORY_FILE_OPS.md) — pipelines multi-app (Pepeline / FILE_OPS)
