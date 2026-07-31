# definition_app_PROFILE_SEED — Definición PROFILE_SEED

Carpeta de documentación de análisis y definición para **PROFILE_SEED** (Sembrador de perfiles), vertical de la familia reutilización alta.

> **Producto:** [`../PROFILE_SEED.md`](../PROFILE_SEED.md)  
> **Familia §2:** [`../APP_FACTORY_HIGH_REUSE.md`](../APP_FACTORY_HIGH_REUSE.md) §7  
> **Rama Git:** `feature/profile-seed` (no desplegar a producción hasta merge a `main`)  
> **Chasis:** reutiliza `Company`, `UserProfile`, `Project`, `ProjectMembership`, seguridad y billing.  
> **Reuso técnico:** snapshots de `DmsSourceProfile` / contrato GATE / perfiles Match / entrada Reverse — **clone**, no vínculo vivo; escritura vía `save_source` (patrón Scout apply).  
> **Complemento:** Structure Scout (desde muestra); Bridge GATE (pre-check por hash).  
> **Integración:** [`ps_integration.md`](ps_integration.md) (as-built M1–M4).

---

## Método de trabajo (por módulo)

Igual que FILE GATE / Match / Reverse / Scout: **definir → prototipar → revisar → implementar solo con OK explícito**.

```mermaid
flowchart LR
    A[Doc en definition_app_PROFILE_SEED] --> B[Prototipo HTML]
    B --> C[Revisión UX]
    C --> D{OK?}
    D -->|No| A
    D -->|Sí| E[Usuario: Desarrolla el módulo]
    E --> F[Código apps/templates o CTAs]
```

| Paso | Dónde | Quién |
|------|-------|--------|
| 1. Diseño | `docs/definition_app_PROFILE_SEED/<modulo>.md` | Agente + revisión |
| 2. HTML demo | `prototype/profile_seed/` | Agente |
| 3. Revisión | Chat / navegador | Usuario |
| 4. Implementación | Servicios + CTAs (MVP) o `apps/profile_seed/` | Solo con «Desarrolla el módulo» |

---

## Documentos (por módulo)

| Archivo | Módulo | Contenido | Estado |
|---------|--------|-----------|--------|
| [`../PROFILE_SEED.md`](../PROFILE_SEED.md) | Producto | Visión, MVP, fronteras, roles | **En desarrollo** (M1–M4) |
| [`seed_hub.md`](seed_hub.md) | **1** | Hub / CTA Importar / permisos | **Implementado** |
| [`source_picker.md`](source_picker.md) | **2** | Selector origen (kind, proyecto, versión, slot) | **Implementado** |
| [`apply_draft.md`](apply_draft.md) | **3** | Preview, validación, escritura borrador | **Implementado** |
| [`seed_history.md`](seed_history.md) | **4** | Historial / auditoría de semillas | **Implementado** |
| [`ps_integration.md`](ps_integration.md) | Transversal | Kind opcional, URLs, reuso DMS, roles | **Documentado** |

---

## Prioridad de siembra (MVP)

| Prioridad | Origen → Destino | Estado |
|-----------|------------------|--------|
| P0 | FILE GATE (esquema publicado) → FILE MATCH Perfil A | **Hecho** |
| P1 | FILE GATE → FILE MATCH Perfil B | Pendiente |
| P2 | FILE GATE → Reverse (entrada) | Pendiente |
| P3 | Match A ↔ Match B / otro Match | Pendiente |

---

## Carpetas de trabajo

| Rol | Ruta |
|-----|------|
| Specs | `docs/definition_app_PROFILE_SEED/` |
| Prototipos | `prototype/profile_seed/` (gitignored) |
| Templates | `templates/profile_seed/` + CTAs en `templates/file_match/` |
| App / servicios | `apps/profile_seed/` |

---

## Decisiones de diseño (hereda del producto)

| # | Tema | Decisión |
|---|------|----------|
| PS1 | ¿Compartir perfil vivo? | **No** — solo clone snapshot |
| PS2 | ¿Auto-publicar? | **No** — solo borrador destino |
| PS3 | ¿Tenant? | Misma compañía |
| PS4 | ¿Vs Scout? | Seed = desde definición; Scout = desde muestra |
| PS5 | ¿Vs Bridge GATE? | Seed = estructura; Bridge = job passed por hash |
| PS6 | ¿Kind en MVP? | **No obligatorio** — servicios + CTAs primero |

---

## Orden de apertura

| Orden | Qué | Estado |
|-------|-----|--------|
| 0 | README + `PROFILE_SEED.md` | **Hecho** |
| 1 | `seed_hub.md` | **Implementado** |
| 2 | `source_picker.md` | **Implementado** |
| 3 | `apply_draft.md` | **Implementado** |
| 4 | `seed_history.md` | **Implementado** |
| 5 | `ps_integration.md` | **Documentado** |
| 6 | PR a `main` | Pendiente |

---

## Índice y estado

| Documento | Estado |
|-----------|--------|
| Producto PROFILE_SEED | [`../PROFILE_SEED.md`](../PROFILE_SEED.md) — M1–M4 en `feature/profile-seed` |
| Integración | [`ps_integration.md`](ps_integration.md) |
| Paraguas familia | [`../APP_FACTORY_HIGH_REUSE.md`](../APP_FACTORY_HIGH_REUSE.md) §7 |
| Código | `apps/profile_seed/` · host Match Perfil A |

---

*Carpeta: `docs/definition_app_PROFILE_SEED/` — definición por módulo del Sembrador de perfiles.*
