# Módulo D — Dashboard (FILE PIPELINE)

Tablero de corridas en el alcance de pipelines **autorizados**. Dry-run excluido del pulso operativo.

> **Estado:** implementado  
> **Producto:** [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md)  
> **Plantillas:** `templates/file_pipeline/dashboard/`

---

## Propósito

Vista de compañía (UF autorizado): volumen de runs, canales (`trigger_source`), fallos recientes. No sustituye el historial por pipeline.

---

## Alcance

- Solo pipelines que el usuario puede ver (compañía o membresía).  
- No mezclar datos de otras compañías.  
- Enlaces a hub / historial / detalle de run.

---

## URLs

| Acción | Ruta |
|--------|------|
| Tablero | `tablero/` |
| Ayuda | `tablero/ayuda/` |


## Relacionados

[`project_lifecycle.md`](project_lifecycle.md) · [`pipeline_history.md`](pipeline_history.md)
