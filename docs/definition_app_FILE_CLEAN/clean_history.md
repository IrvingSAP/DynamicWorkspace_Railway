# Módulo 6 — Historial (FILE CLEAN)

> **App:** File Clean  
> **Estado:** implementado

---

## Objetivo

Listar y detallar jobs de limpieza del proyecto: quién, cuándo, versión, hashes, estado, métricas, enlaces a artifacts (según TTL y rol).

---

## Listado

Columnas sugeridas: fecha, usuario/servicio, versión, estado, filas, cambios, acciones (detalle / descargas si vigentes).

Filtros: estado, rango de fechas, usuario, archivo, hash, versión, tipo (ejecución / preview), TTL.

---

## Detalle

- Metadatos del job.  
- Resumen de reglas aplicadas (conteo por `code`).  
- Descargas si no expiraron.  
- CO: metadatos; política de descarga de contenido alineada a Gate (sin PII innecesaria para CO si se decide igual).

---

## API-ready

`GET /api/v1/jobs/{id}` futuro reutilizará la misma proyección de detalle (campos estables).

---

## Criterio de aceptación

- [x] Listado + detalle  
- [x] Respeto TTL artifacts (7 días)  
- [x] Roles CO vs GE/PA

## Implementación

| Pieza | Ruta |
|-------|------|
| Servicio | `apps/file_clean/history/services/clean_history_service.py` |
| Vistas | `apps/file_clean/history/views.py` |
| UI | `templates/file_clean/history/` · URLs `/historial/` |
| TTL | `clean_run_service.ARTIFACT_TTL` (= `DOWNLOAD_TTL`) |
