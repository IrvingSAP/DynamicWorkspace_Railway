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

---

## UI

- Resumen de perfil + conteo de reglas.  
- Confirmación “Publicar vN”.  
- Mensaje de éxito + CTA a Ejecutar.

---

## API-ready

`version=published` en PLATFORM_API resolverá `current_version` de CleanConfig — mismo patrón Gate/Pipe.

---

## Criterio de aceptación

- [ ] Validaciones P1–P4  
- [ ] Historial de versiones consultable (metadatos)  
- [ ] Mensajes UI_MESSAGES
