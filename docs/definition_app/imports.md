# apps.imports

Importación de datos desde Excel.

---

## Propósito

Acelerar adopción permitiendo cargar un Excel existente y crear campos + registros automáticamente.

---

## Responsabilidades

| Sí | No |
|----|-----|
| Wizard: subir → analizar → mapear → confirmar | Exportación (Fase 2, posible app `exports`) |
| Detección de tipos de columna | Diseño manual de campos |
| Creación masiva de `FieldDefinition` y `Record` | Validación TOTP |

---

## Flujo

```
Excel → Análisis columnas → Vista previa → Mapeo manual (opcional)
     → Crear campos → Cargar registros → Reporte errores
```

---

## Reglas

- Permiso `import` requerido (PA, ED).
- Límite de filas por importación configurable.
- Transacción por lote; filas con error no detienen el resto (reporte al final).
- Librería sugerida: `openpyxl`.

> **No confundir** con aprovisionamiento masivo de **usuarios UF** (`apps.accounts`) — ver [`accounts_provisioning.md`](accounts_provisioning.md) (**pendiente** Fase 1+).

---

## URLs previstas

| URL | Permiso |
|-----|---------|
| `/app/proyectos/<slug>/importar/` | `import` |

---

## Dependencias

- `apps.projects`
- `apps.fields`
- `apps.records`

## Fase

**Fase 2** — adopción.

## Documentos relacionados

- [`projects.md`](projects.md)
- [`fields.md`](fields.md)
- [`records.md`](records.md)
- [`accounts_provisioning.md`](accounts_provisioning.md) — dominio distinto (usuarios UF)
