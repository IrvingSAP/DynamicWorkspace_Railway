# Módulo 2 — Diseñador de pasos (FILE PIPELINE)

Rail ordenable de pasos: cada uno es `kind` del **Pipeline Step Catalog** + proyecto **activo** de esa app.

> **Estado:** implementado (MVP catálogo en código; CRUD plataforma = M2b)  
> **Producto:** [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §5–§5.1, §6  
> **Catálogo:** [`pipeline_catalog.md`](pipeline_catalog.md)  
> **Prototipo:** `prototype/file_pipeline/pipeline_designer.html`

---

## Propósito

Editar el **borrador** de la versión siguiente. No elige versiones numéricas de cada app: el run usará la **versión publicada activa** de cada proyecto de paso.

**Completar el módulo (hub paso 1):** guardar el rail con ≥1 paso válido (kind habilitado, proyecto de la compañía, handoff coherente en lo que el diseñador pueda validar en caliente).

Sin ese guardado, **Publicar** se rechaza ([`pipeline_publish.md`](pipeline_publish.md)).

---

## Datos de un paso (borrador)

| Campo | Notas |
|-------|--------|
| `order` | Entero; único |
| `kind` | Solo catálogo con `pipeline_enabled=true` y no `disabled` |
| `project_ref` | Proyecto activo, misma compañía, `project_kind` alineado al kind |
| `on_error` | MVP: `stop` |
| `input_from` | `pipeline_input` (paso 1) o `previous` |
| `options` | JSON mínimo (p. ej. Match A/B en fase posterior) |

---

## UX

- Picker de kind → lista de proyectos autorizados activos de ese kind.  
- Rail: subir / bajar / quitar / editar.  
- Firma visual: **nodos OK / pendiente**, no canvas tipo n8n.  
- Ayuda: `pipeline_designer_help.html`.

**Guardar borrador:** persiste el rail; marca hub «Diseñar pasos» completo.

---

## Validaciones en diseño (suaves)

| Check | Efecto |
|-------|--------|
| Kind fuera de catálogo | No ofrecer / no guardar |
| Proyecto de otra compañía o inactivo | Rechazo |
| 0 pasos | Guardar permitido como incompleto; **no** completa el módulo 1 del hub |
| Handoff dudoso | Aviso; bloqueo duro al **publicar** |

---

## URLs (objetivo)

| Acción | Ruta tentativa |
|--------|----------------|
| Diseñador | `pipelines/<slug>/disenar/` |
| Ayuda | `pipelines/<slug>/disenar/ayuda/` |

---

## Relacionados

[`pipeline_catalog.md`](pipeline_catalog.md) · [`pipeline_publish.md`](pipeline_publish.md) · [`fp_integration.md`](fp_integration.md)
