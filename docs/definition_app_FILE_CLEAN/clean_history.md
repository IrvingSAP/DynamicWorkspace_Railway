# Módulo 6 — Historial (FILE CLEAN)

> **App:** File Clean  
> **Estado:** borrador de definición

---

## Objetivo

Listar y detallar jobs de limpieza del proyecto: quién, cuándo, versión, hashes, estado, métricas, enlaces a artifacts (según TTL y rol).

---

## Listado

Columnas sugeridas: fecha, usuario/servicio, versión, estado, filas, cambios, acciones (detalle / descargas si vigentes).

Filtros: estado, rango de fechas.

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

- [ ] Listado + detalle  
- [ ] Respeto TTL artifacts  
- [ ] Roles CO vs GE/PA
