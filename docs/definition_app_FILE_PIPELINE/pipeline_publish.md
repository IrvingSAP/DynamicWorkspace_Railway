# Módulo 3 — Publicar versión (FILE PIPELINE)

Congela el snapshot de pasos del borrador. Los runs usan **solo** esa versión.

> **Estado:** implementado  
> **Producto:** [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §6, §12  
> **Prototipo:** `prototype/file_pipeline/pipeline_publish.html`

---

## Propósito

Paridad Clean/SM: publicar es irreversible para esa `version_number`; se abre borrador `N+1`.

---

## Gate del hub (paso 1)

Si **Diseñar pasos** no está completo (rail no guardado o 0 pasos válidos):

- El botón Publicar **no** ejecuta la publicación (no usar `disabled` HTML que traga el click).  
- `aria-disabled` + alerta:

> No puede publicar. Pasos no completados: Diseñar pasos.

Misma familia que Split/Merge (`UI_MESSAGES` publicar con pasos pendientes).

---

## Checklist al publicar (si Diseñar está completo)

| Id | Check |
|----|--------|
| P1 | ≥1 paso en el snapshot |
| P2 | Cada `kind` en catálogo y habilitado |
| P3 | Cada proyecto con versión **publicada** activa |
| P4 | Handoffs tipados |
| P5 | El publicador puede usar los proyectos de paso |

Fallo → no publica; `user_message` + `errors` por check.

---

## Efecto

- `PipelineVersion` published inmutable.  
- `current_version` apunta a ella.  
- Para disparar: además `PipelineDefinition.status = active`.

---

## URLs (objetivo)

`pipelines/<slug>/publicar/`

---

## Relacionados

[`project_lifecycle.md`](project_lifecycle.md) · [`pipeline_designer.md`](pipeline_designer.md) · [`../definition_app/UI_MESSAGES.md`](../definition_app/UI_MESSAGES.md)
