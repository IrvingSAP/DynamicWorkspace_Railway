# Módulo 2 — Perfil de lectura (FILE CLEAN)

> **App:** File Clean  
> **Estado:** borrador de definición  
> **Reuso:** [`../definition_app_DMS/source_definition.md`](../definition_app_DMS/source_definition.md) (asistente / forma SourceProfile)

---

## Objetivo

Definir **cómo se lee** el archivo a limpiar: tipo, encoding, delimitador/posiciones, hoja, encabezados y lista de campos. Clean no inventa un segundo parser.

---

## Alcance MVP

| Incluye | Excluye |
|---------|---------|
| Tipos soportados por parsers DMS activos | Diseñar layout destino de negocio |
| Campos con nombre interno + metadatos mínimos | Validación de obligatoriedad tipo Gate (eso es Gate) |
| Encoding / BOM como parte del perfil | Detección automática completa (eso es Scout; opcional “importar desde Scout” Fase 2) |

---

## Flujo

```text
Elegir tipo de archivo
  → Parámetros de captura (delimitador, posiciones, hoja…)
  → Definir / importar campos
  → Guardar en borrador de versión Clean
```

---

## Relación con reglas (M3)

- Las reglas por campo referencian el **nombre interno** del perfil (`field_name`).  
- Reglas globales (`dedupe_rows`, `encoding_normalize` a nivel archivo) no requieren campo.  
- Renombrar o eliminar un campo del perfil **invalida** reglas que lo referencian hasta corregirlas (bloqueo al guardar perfil y/o al publicar — P5 en [`clean_publish.md`](clean_publish.md)).  
- `compose` con token `{field:X}` exige que `X` exista en el perfil (misma fila).  
- Detalle de ops: [`clean_rules.md`](clean_rules.md).

---

## API-ready

El perfil publicado viaja dentro de la **versión** del proyecto. La API futura solo envía el archivo; no reenvía el perfil.

---

## Criterio de aceptación

- [x] Reuso máximo de UI/servicios source (skin Clean)  
- [x] Guardado en borrador sin publicar  
- [x] Validación de tipo/extensión alineada a catálogo DMS  
- [ ] Guardar/avisar si hay reglas que apuntan a campos borrados o renombrados (cuando exista M3)
