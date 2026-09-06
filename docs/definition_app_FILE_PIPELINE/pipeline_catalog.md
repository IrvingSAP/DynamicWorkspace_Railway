# Módulo 2b — Pipeline Step Catalog (FILE PIPELINE)

Inventario **opt-in** de `kind` que el diseñador puede ofrecer como paso.

> **Estado:** implementado (CRUD plataforma UA; diseñador lee la tabla)  
> **Producto:** [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §5.1  
> **Audiencia:** operador de **plataforma** (no UF de compañía)  
> **Prototipo:** `pipeline_catalog.html` y pantallas CRUD asociadas

---

## Propósito

Una app en el menú **no** entra sola al orquestador. Hace falta registro + `pipeline_enabled`.

| Campo | Uso |
|-------|-----|
| `kind` | Código estable (`file_gate`, `file_clean`, `dms`, …) |
| `label` | Texto en el diseñador |
| `project_kind` | Debe coincidir con `Project.project_kind` |
| `runner` | Servicio `run_*_job` |
| `input_arity` / `output_arity` | Handoff |
| `pipeline_enabled` | Opt-in |
| `mvp_phase` | `A` / `B` / `C` |
| `status` | `active` · `deprecated` · `disabled` |

Este `status` del **kind** no es el `PipelineDefinition.status` (Activo / En proceso / Inactivo).

---

## UX (plataforma)

- Listado de kinds, flags compañía × catálogo.  
- Alta / edición / deshabilitar.  
- Ayuda: por qué una app nueva no aparece en el diseñador.

**Runtime:** tabla `PipelineStepKind` + flags `PipelineCompanyKindFlag`. Seed inicial (Clean, Gate, Split/Merge, Pipe, Reverse, Match enabled; Scout/Repair off). CRUD UA en `/app/file-pipeline/catalogo/`.

---

## Relacionados

[`pipeline_designer.md`](pipeline_designer.md) · [`../PLATFORM_API.md`](../PLATFORM_API.md) · [`fp_integration.md`](fp_integration.md)
