# Prototipos HTML

Resumen del flujo de prototipos. Detalle completo en [`../../prototype/README.md`](../../prototype/README.md).

## Ubicación

```
prototype/<app>/<app>_<accion>.html
```

Ejemplo: `prototype/company/company_list.html`

## Ciclo de vida

1. Crear HTML en `prototype/<app>/`
2. Revisar y validar (UX, campos, permisos)
3. Tras **OK** → crear `templates/<app>/<app>_<accion>.html` extendiendo `app_base.html` + vista Python
4. Aplicar reglas de mensajes de [`UI_MESSAGES.md`](UI_MESSAGES.md) en vista, servicio y template
5. **Eliminar** el archivo de `prototype/<app>/`

## Nombrado

Idéntico al de producción — ver [`VISTAS.md`](VISTAS.md#10-naming--prefijo-de-app-obligatorio).

## Regla clave

Los prototipos son **temporales**. No deben coexistir con la plantilla final en `templates/`.

## Tablas

Todas las tablas de listado usan [DataTables](https://datatables.net/manual/). Ver [`VISTAS.md` §10.6](VISTAS.md#106-tablas-html--datatables).

### Layout de listados

Patrón obligatorio para nuevas pantallas de listado: [`VISTAS.md` §10.8](VISTAS.md#108-cobertura-de-pantalla-layout). Referencia implementada: `templates/company/company_list.html`, `templates/accounts/account_list.html`. Prototipos alineados: `prototype/projects/project_list.html`, `project_members.html`, `prototype/fields/field_list.html`, `prototype/records/record_list.html`.

- Listados: `app-main--wide` + `panel panel--table` + `table-dt-host`
- Formularios y detalle: `app-main` estándar (sin `--wide`)

## Plantilla base Django

La zona `/app/` usa `templates/app_base.html` + `static/css/app.css` + `static/js/dw-modals.js`. Ejemplos migrados: `templates/company/company_list.html`, `prototype/accounts/` (list dual + CRUD unificado).

El sitio público usa `templates/public/base.html` + `static/css/public.css`.

## Guías de flujos (migradas)

| Prototipo | Producción | Documentación |
|-----------|------------|---------------|
| `prototype/help/uf_guide.html` | `templates/help/uf_guide.html` → `/app/ayuda/` | [`help.md`](help.md) |
| `prototype/public/public_help.html` | `templates/public/help.html` → `/ayuda/` | [`public.md`](public.md) |

Estáticos: `static/js/guide-spine.js` (compartido), `static/css/help.css` (UF), sección guía en `static/css/public.css`.
