# Módulo 4 — Ejecutar pipeline (FILE PIPELINE)

Disparo UI: upload de entrada, orquestación lineal, informe por paso.

> **Estado:** implementado  
> **Producto:** [`../FILE_PIPELINE.md`](../FILE_PIPELINE.md) §7, §7.1, §9  
> **Prototipo:** `pipeline_run.html`, `pipeline_result.html`

---

## Propósito

Ejecutar la **versión publicada** del pipeline. El orquestador pasa artifacts por referencia (sin re-upload entre apps).

**Requisitos:** `status=active`, versión publicada, actor autorizado en pipeline **y** en cada proyecto de paso.

---

## Datos del run

| Campo | Notas |
|-------|--------|
| `trigger_source` | UI → `ui` |
| `dry_run` | Opcional |
| `status` | `queued` · `running` · `completed` · `failed` · `cancelled` |
| Por paso | `pending` · `running` · `completed` · `failed` · `skipped` |

MVP: `on_error=stop` → primer fallo deja el resto `skipped`.

---

## UX

- Upload archivo(s) según aridad del primer paso.  
- Resultado: rail OK / ERROR / omitido + enlace a `app_job_id` de cada app.  
- No sustituye el historial local de cada app.

---

## URLs (objetivo)

| Acción | Ruta tentativa |
|--------|----------------|
| Ejecutar | `pipelines/<slug>/ejecutar/` |
| Resultado | `pipelines/<slug>/runs/<id>/` |

---

## Relacionados

[`pipeline_history.md`](pipeline_history.md) · [`fp_integration.md`](fp_integration.md) · [`../PLATFORM_API.md`](../PLATFORM_API.md)
