# Módulo 4 — Publicar versión (FILE SPLIT / MERGE)

Definición e implementación de **publicar** el borrador: congela **perfil de lectura + operation + sm_rules** en una `DmsMappingVersion` inmutable.

> **Estado:** implementado (M4)  
> **Producto:** [`../FILE_SPLIT_MERGE.md`](../FILE_SPLIT_MERGE.md)  
> **Integración:** [`sm_integration.md`](sm_integration.md)  
> **Dependencia:** M2 + M3 (`sm_profile.md`, `sm_rules.md`)  
> **Rama:** fusionada a `main` (PR #13)  
> **Patrón hermano:** [`../definition_app_FILE_CLEAN/clean_publish.md`](../definition_app_FILE_CLEAN/clean_publish.md)

---

## Objetivo

Permitir al PA/ED congelar la definición ejecutable:

```text
Perfil completo (M2) + operación/reglas (M3)
  → Checklist P1–P5
  → Publicar vN
  → current_version = vN (inmutable)
  → Nuevo borrador vN+1 (copia editable)
  → (M5) Ejecutar solo contra published
```

Copy: **versión publicada**, no “deploy” ni “release” de producto.

---

## Qué no es

| No | Motivo |
|----|--------|
| Upload / job / artifacts | M5 |
| Historial de corridas | M6 |
| PLATFORM_API HTTP | Post FILE_OPS; snapshot ya es API-ready |

---

## Reglas

| ID | Regla |
|----|--------|
| P1 | No publicar sin perfil válido (tipo, captura, ≥1 campo; `validate_source_dict` strict). |
| P2 | No publicar sin `rules_complete` (operación + reglas ON según M3). |
| P3 | Publicar marca el borrador como `published`, fija `DmsProjectConfig.current_version` e incrementa el siguiente borrador. |
| P4 | Jobs en curso no cambian de definición a mitad (referencia a versión del job — M5). |
| P5 | Toda regla **habilitada** debe pasar validación de `code` + `params` + campos del perfil. Deshabilitadas no bloquean. |

---

## Validación al publicar (P5)

Al publicar se revalida el pipeline completo. Fallo → **no** publica.

| Check | Rechazo si… |
|-------|-------------|
| Perfil | Sin tipo/campos o errores strict |
| Operación | Ausente o no `split`/`merge` |
| Completitud | No cumple `is_rules_complete` |
| Reglas ON | Params inválidos o campo inexistente |

---

## Pantallas y URLs

Prefijo: `/app/file-split-merge/proyectos/<slug>/publicar/`

| Pantalla | URL | Nombre |
|----------|-----|--------|
| Hub publicar | `` | `publish_hub` |
| Ayuda | `ayuda/` | `publish_hub_help` |
| Acción publicar (POST) | `ejecutar/` | `publish_action` |

---

## Flujo UX

1. Hub M1 → CTA Publicar (activo si `profile_complete`; primario si `rules_complete` y aún no publicada).  
2. Hub publicar: strip de versiones, checklist, resumen (tipo, campos, operación, reglas ON), historial de versiones.  
3. Confirmación «Publicar vN» (JS compartido `source_profile-publish.js`).  
4. Éxito → mensaje + nuevo borrador; CTA Ejecutar deshabilitado hasta M5.

---

## Integración técnica

| Pieza | Uso |
|-------|-----|
| `DmsMappingVersion` | Borrador → published; nuevo draft clonado |
| `DmsProjectConfig.current_version` | Versión activa para M5 |
| `DmsSourceProfile.config["sm_rules"]` | Congelado en el snapshot |
| `split_merge_publish_service` | Checklist, validate, publish |

---

## API-ready

`version=published` resolverá `current_version`. El runner (M5 / PLATFORM_API) no lee el borrador.

---

## Criterio de aceptación

- [x] Validaciones P1–P5  
- [x] Snapshot incluye perfil + operation + rules  
- [x] Historial de versiones (metadatos)  
- [x] Mensajes UI_MESSAGES §3.15 M4  
- [x] Hub M1 refleja versión activa y stepper  
