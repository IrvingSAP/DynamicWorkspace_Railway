# Módulo 3 — Reglas de limpieza (FILE CLEAN)

> **App:** File Clean  
> **Estado:** borrador de definición  
> **Reuso:** motor de reglas FilePipe / DMS (sin fork de pipeline ETL)

---

## Objetivo

Mantener un **catálogo ordenado** de reglas de limpieza aplicables al perfil de lectura, editables en borrador y congeladas al publicar.

---

## Principios

1. **Explícitas** — nada se limpia si no hay regla.  
2. **Ordenadas** — el orden de aplicación es parte del contrato.  
3. **Auditables** — cada aplicación produce entrada en el change log del job.  
4. **Compartidas** — mismas implementaciones que DMS cuando el `code` exista; Clean solo filtra el subset “limpieza”.

---

## Modelo de una regla

| Campo | Descripción |
|-------|-------------|
| `code` | Identificador (`trim`, `case_upper`, `date_normalize`, …) |
| `field_name` | Null = global; si no, campo del perfil |
| `params` | JSON (formato fecha, mapa replace, clave dedupe…) |
| `enabled` | Bool |
| `sort_order` | Entero |

---

## Catálogo MVP (subset)

Ver tabla en [`../FILE_CLEAN.md`](../FILE_CLEAN.md) §8. Prioridad de implementación:

| Prioridad | Codes |
|-----------|--------|
| P0 | `trim`, `strip_invisible`, `case_upper`, `case_lower`, `null_tokens` |
| P1 | `date_normalize`, `number_normalize`, `replace_map` |
| P2 | `dedupe_rows`, `encoding_normalize` |

---

## UI

- Lista ordenable (drag o subir/bajar).  
- Alta desde catálogo permitido (no free-text de código).  
- Preview de efecto en M5 (run), no aquí.

---

## Frontera con FilePipe

| Clean | Pipe |
|-------|------|
| Reglas de normalización pre-calidad | Reglas + mapeo hacia destino de negocio |
| Salida ≈ mismo esquema de lectura | Salida = TargetProfile |

Compartir librería de operadores; **no** copiar pantallas de mapeo N:1 / calculados al MVP Clean.

---

## API-ready

Las reglas viven en la versión publicada. API no acepta “rules inline” en MVP de plataforma.

---

## Criterio de aceptación

- [ ] CRUD de reglas en borrador  
- [ ] Orden persistente  
- [ ] Rechazo de `code` desconocido  
- [ ] Documentado el subset vs catálogo DMS completo
