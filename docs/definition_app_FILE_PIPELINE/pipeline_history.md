# Módulo 5 — Historial y auditoría (FILE PIPELINE)

Listado de runs y detalle con disparo (§7.1 del producto).

> **Estado:** implementado  
> **Producto:** [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §7.1, §10  
> **Plantillas:** `templates/file_pipeline/history/`

---

## Propósito

Auditar **quién/qué** disparó, **qué versión**, **timing**, hashes de entrada y cierre de cada paso (`app_job_id`, `error_code`).

---

## Filtros del listado

`trigger_source` (ui / api / watch / scheduler / dependency), estado del run, fechas.  
No filtrar aquí el `status` de la **definición** (eso es M1).

---

## Detalle

- Disparo: actor, API client, `idempotency_key`, `correlation_id`.  
- Rail de step runs.  
- Enlaces a jobs nativos de cada app.

CO: metadatos; descarga de contenido según política de las apps.

Borrado del historial del orquestador: quien disparó la corrida (o el PA) puede eliminar el registro. No borra el job nativo de cada app. No aplica a runs en cola o en curso.

---

## URLs (objetivo)

| Acción | Ruta tentativa |
|--------|----------------|
| Historial | `pipelines/<slug>/historial/` |
| Detalle | `pipelines/<slug>/runs/<id>/auditoria/` |
| Eliminar corrida | `POST pipelines/<slug>/runs/<id>/eliminar/` |
| Eliminar propias | `POST pipelines/<slug>/historial/eliminar-mias/` |

---

## Relacionados

[`pipeline_run.md`](pipeline_run.md) · [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §7.1
