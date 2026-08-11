# Módulo 4 — Publicar versión (FILE CLEAN)

> **App:** File Clean  
> **Estado:** borrador de definición

---

## Objetivo

Congelar **perfil de lectura + reglas** en una versión inmutable ejecutable (`published`). El borrador sigue editable para la siguiente versión.

---

## Reglas

| ID | Regla |
|----|--------|
| P1 | No publicar sin al menos un campo en el perfil (salvo tipos sin campos — no aplica MVP). |
| P2 | No publicar sin al menos una regla habilitada (evitar proyectos vacíos). |
| P3 | Publicar incrementa `version_number`; ejecuciones apuntan a `current_version`. |
| P4 | Jobs en curso no cambian de definición a mitad (referencia a versión del job). |
| P5 | Toda regla **habilitada** debe pasar validación de `code` + `params` + referencias a campos (ver abajo y [`clean_rules.md`](clean_rules.md)). |

---

## Validación de reglas al publicar (P5)

Al publicar se revalida el pipeline completo (no solo lo guardado en borrador). Fallo → **no** publica; errores inline / `messages.*` con `error_code`.

| Check | Rechazo si… | `error_code` sugerido |
|-------|-------------|------------------------|
| `code` en subset Clean | Código desconocido o no permitido | `file_clean_rule_unknown` |
| `field_name` (reglas de campo) | Nombre no existe en el perfil de la versión | `file_clean_rule_field_missing` |
| `replace_map` | Falta `map`, no es objeto, o `map` vacío | `file_clean_replace_map_invalid` |
| `replace` | Falta `find` o `find` es `""` | `file_clean_replace_find_required` |
| `compose` | Falta `template`, token desconocido, o `{field:X}` con X inexistente | `file_clean_compose_invalid` |
| Reglas globales | `dedupe_rows` sin clave; `encoding_normalize` sin params mínimos si se exigen | según op |

Reglas **deshabilitadas** (`enabled=false`) no bloquean publicar, pero si se reactivan en un borrador posterior deben validarse al guardar o al siguiente publish.

Detalle de contrato por op: [`clean_rules.md`](clean_rules.md) § semántica y § validaciones.

---

## UI

- Resumen de perfil + conteo de reglas (habilitadas / total).  
- Si P5 falla: listar reglas inválidas (code + campo + motivo).  
- Confirmación “Publicar vN”.  
- Mensaje de éxito + CTA a Ejecutar.

---

## API-ready

`version=published` en PLATFORM_API resolverá `current_version` de CleanConfig — mismo patrón Gate/Pipe.  
Una versión publicada implica params ya validados (P5); la API no reenvía reglas.

---

## Criterio de aceptación

- [x] Validaciones P1–P5  
- [x] Rechazo de publish con `replace`/`replace_map`/`compose` inválidos  
- [x] Historial de versiones consultable (metadatos)  
- [x] Mensajes UI_MESSAGES
