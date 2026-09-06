# Manual de uso — PLATFORM API

Guía para un usuario que **nunca ha usado** la API de DynamicWorkspace. No sustituye las pantallas de Gate, Pipe u otras apps: esas **diseñan** el trabajo; aquí se **identifica la máquina** y se **dispara** el mismo trabajo por HTTP.

Este manual cubre el circuito de **jobs sueltos** (whoami, validate, run, detalle, report, output, listado, auditoría de cliente, rotar/cancelar). El circuito de **pipelines** publicados (`kind=file_pipeline`) va en un segundo manual con el mismo esquema (pasos, curl, Postman, errores): [`MANUAL_USUARIO_API_PIPELINE.md`](MANUAL_USUARIO_API_PIPELINE.md).

**Cómo usamos este documento:** un paso a la vez. Los Pasos **1 a 10** (consola + **curl**) están **hechos** (`api-qa-p01` revocado). Postman **6–8 hechos**; **10 A–C Postman** siguen opcionales (misma semántica ya vista en curl). El circuito de pipelines: [`MANUAL_USUARIO_API_PIPELINE.md`](MANUAL_USUARIO_API_PIPELINE.md).

Fuentes de producto: [`PLATFORM_API.md`](../PLATFORM_API.md) §3–§5 · §4.2 · §10.2 · [`pa_auth.md`](pa_auth.md) · [`pa_contract.md`](pa_contract.md) · [`pa_openapi.md`](pa_openapi.md) · [`pa_integration.md`](pa_integration.md) · [`pa_security.md`](pa_security.md) · [`pa_jobs_run.md`](pa_jobs_run.md) · [`pa_jobs_query.md`](pa_jobs_query.md) · [`pa_client_audit.md`](pa_client_audit.md) · [`pa_audit.md`](pa_audit.md). Scopes en pantalla: `jobs:run`, `jobs:read`, `jobs:cancel`, `pipeline:run`, `artifacts:download`.

---

## Postman — misma API que curl (pendiente)

El navegador **no** envía `Authorization: Bearer` al pegar una URL `/api/v1/…`. Postman sí: es **la misma petición HTTP** que `curl.exe` (método, URL, Bearer y, si aplica, form-data o query). La cookie US/UF **no** autentica estas rutas.

**Estado:** Postman **6 A–C, 7 y 8 A–D hechos.** **10 A–C curl/UI hechos** (sandbox cerrado). Postman 10 A–C **pendientes** (opcionales).

### 1. Entorno (una vez)

Cree un Environment, p. ej. `DW local`:

| Variable | Valor |
|---------|--------|
| `base` | `http://127.0.0.1:8000` |
| `key` | la key sandbox (`dw_test_…`), **sin** la palabra `Bearer` |

En **cada** request: pestaña **Authorization** → Type **Bearer Token** → Token `{{key}}`. Postman añade el header `Authorization: Bearer …`. **No** ponga otra vez `Bearer` en el token.

Si usa **Header** crudo (en lugar de la pestaña Auth): el valor debe ser `Bearer ` + la key, **un solo espacio**. No cree ese header **y** Bearer Token a la vez (duplica y suele dar 401).

### 2. Importar un curl

**Import → Raw text** → pegue el `curl.exe …` del paso (puede dejar solo `curl`). Postman arma método, URL y headers. Revise **Body**: los `-F` deben quedar como **form-data**, no JSON.

### 3. ¿Header y Body? (Paso 6 y el resto)

| Request | ¿Crear Header a mano? | ¿Body? |
|---------|------------------------|--------|
| **6 A** `whoami` | No. Solo Auth Bearer Token. GET **no** lleva cuerpo. | **none** |
| **6 B** `validate` | No. No añada `Authorization` otra vez. No ponga `Content-Type` a mano si usa form-data. | **Sí:** form-data Text (`kind`, `project_slug`, `wait`). **Sin** fila `file` |
| **6 C** `contract` | Igual que whoami | **none** |
| **7** `run` | Auth + header `Idempotency-Key` | form-data + **File** en `file` |
| **8 A** detalle | No | **none** |
| **8 B** report | No | **none** (luego Save Response → archivo) |
| **8 C** output | No | **none** (este Split: 404 JSON) |
| **8 D** listado | No | **none**. Query en pestaña **Params** (`kind`, `limit`) |
| **10 B** cancel | No | **none** (POST vacío). Split completed: 409 |

**Error típico Paso 6:** en Token escribir `Bearer dw_test_…` → 401. Solo la key.

### 4. Equivalencia rápida (misma prueba Split)

| Paso | Postman |
|-------|--------|
| 6 A | `GET` `{{base}}/api/v1/whoami` · Auth Bearer · Body none · **hecho** (`api-qa-p01`, ACME, sandbox) |
| 6 B | `POST` `{{base}}/api/v1/jobs/validate` · form-data `file_split` / `prueba-02-txtd` / `sync` · **hecho** |
| 6 C | `GET` `{{base}}/api/v1/contract` · **hecho** (`ok`, `kinds` incl. `file_split`, `client_code` api-qa-p01) |
| 7 | `POST` `{{base}}/api/v1/jobs/run` · form-data + File · `Idempotency-Key: prueba-post-001` · **hecho** (replay) |
| 8 A | `GET` `{{base}}/api/v1/jobs/{job_id}` · Body none · **hecho** («Job encontrado.», sin `output_url`) |
| 8 B | `GET` `…/report` · **hecho** (manifiesto `operation: split`, `parts_count: 4`) |
| 8 C | `GET` `…/output` · **hecho** (404 JSON `not_found`, «El artifact no está disponible.») |
| 8 D | `GET` `{{base}}/api/v1/jobs` · **hecho** |
| 10 A | `whoami` vieja 401 / nueva 200 · **curl hecho** · Postman **pendiente** |
| 10 B | `POST` `…/cancel` · **curl hecho** (409 `cancel_not_allowed`) · Postman **pendiente** |
| 10 C | `whoami` tras revocar → 401 · **curl/UI hecho** · Postman **pendiente** |

En el **run**: misma Idempotency-Key + mismo archivo = replay; key nueva = **otro** job.

### 5. Detalles que suelen fallar

- Authorization type **No Auth** y el header mal escrito.  
- Bearer Token con `Bearer dw_test_…` duplicado → 401.  
- Run con Body **raw JSON** y el archivo: el archivo va en **form-data** + tipo **File**.  
- SSL: en `127.0.0.1` use **http**, no `https`.  
- Cookies de sesión US/UF: no las use; es identidad de **máquina**.

Detalle clic a clic de whoami y validate: Paso 6, bloques **Postman**.

---

## Mapa

1. Entrar como administrador de compañía (US) y abrir API — **hecho**  
2. Crear el primer cliente de máquina y copiar la key — **hecho**  
3. Revisar Contrato, Paths e Integración — **hecho**  
4. Política de seguridad (límites de archivo, tasa, TTL) — **hecho**  
5. Tener un proyecto publicado (p. ej. File Gate) y anotar el `project_slug` — **hecho**  
6. Primera llamada HTTP: `whoami` y validar contrato — **curl hecho** · **Postman 6 A–C hechos**  
7. Ejecutar un job (`POST /api/v1/jobs/run`) — **curl hecho** · **Postman hecho** (replay `481ee7ff-…`)  
8. Consultar estado, informe y salida — **curl hecho** · **Postman 8 A–D hechos**  
9. Ver auditoría y qué queda en el historial de la app — **hecho** (pantallas)  
10. Errores frecuentes, rotar/revocar key, cancelar — **curl/UI 10 A–C hechos** · Postman 10 **pendiente** (opcional)

---

## Paso 1 — Entrar como US y abrir el módulo API

### Qué es esto

PLATFORM API no aparece en el menú de operaciones de archivos (UF). La gestiona el **administrador de la compañía (US)**: crea clientes, ve keys, política y auditoría. El ERP u otro sistema usará después un **Bearer**; usted, en este paso, solo entra a la consola web.

### Qué necesita antes

- Una **compañía activa** en DynamicWorkspace.  
- Un usuario de tipo **US** (administrador de compañía), no un usuario de operaciones UF.  
- Contraseña y el flujo de acceso que ya use la compañía (**correo / 2FA** si está activo).  
- El servidor local o el entorno donde corre la app (en desarrollo suele ser `http://127.0.0.1:8000`).

Si aún no tiene compañía ni usuario US, eso se resuelve en **Compañía** y **Usuarios** del menú US, no en API. No siga este paso hasta poder iniciar sesión como US.

### Qué hacer

1. Abra el navegador en `http://127.0.0.1:8000/ingresar/` (o la URL de ingreso de su entorno).  
2. Inicie sesión con el usuario **US**. Complete código de correo o TOTP si el sistema lo pide.  
3. En la barra izquierda debe ver, entre otras, estas entradas: **API**, **Contrato API**, **Paths API**, **Integración API**, **Seguridad API**, **Auditoría API**.  
4. Pulse **API**.  
5. Debe llegar a  
   `http://127.0.0.1:8000/app/platform-api/clientes/`  
   con el título **Clientes de máquina**.

### Qué debe ver

- Texto de que las credenciales son **de esta compañía** y que la key se muestra **una sola vez** al crear o rotar.  
- Resumen (activos / revocados). Si es la primera vez, en **0**.  
- Botón **+ Nuevo cliente**.  
- Enlaces a Contrato, Paths, Seguridad y Auditoría (aún no los use; son pasos posteriores).  
- Si no hay clientes, un listado vacío. Eso es correcto.

### Qué no hacer todavía

- No pulse **+ Nuevo cliente** hasta el Paso 2.  
- No intente `curl` ni Postman: aún no hay key.  
- No entre con un usuario UF: no verá (o no podrá gestionar) este módulo.

### Si algo falla

| Qué ocurre | Qué significa |
|------------|----------------|
| Tras el login no aparece **API** en el menú | No está en perfil US o la sesión no es de administrador de compañía. |
| Mensaje de que solo US gestiona clientes | Entró con un rol que no administra la API. Use un usuario US. |
| La compañía no está activa | Un US/PA debe activar la compañía antes de emitir keys. |
| 404 en `/app/platform-api/clientes/` | No está autenticado o la URL no es de este entorno. Vuelva a `/ingresar/`. |

### Listo para el Paso 2 cuando

Está en **Clientes de máquina**, ve **+ Nuevo cliente**, y entiende que aquí viven las identidades de **sistemas** (ERP, script, integrador), no las de las personas UF.

---

## Paso 2 — Crear el primer cliente y copiar la key

### Qué es esto

Un **cliente de máquina** es la identidad del ERP, script o middleware. No es un usuario UF con 2FA. Queda atado a **esta compañía**, con **scopes** (qué puede hacer) y **una key** que el integrador reutiliza en todas las llamadas ([`PLATFORM_API.md`](../PLATFORM_API.md) §4).

La key se muestra **una sola vez** al crear (o al rotar). DynamicWorkspace guarda un **hash**, no el texto en claro. Si cierra la pantalla sin copiarla, no hay “ver de nuevo”: hay que **rotar** (Paso posterior).

Sandbox y producción son **clientes distintos**, cada uno con su key. En este paso cree solo **Sandbox**.

### Qué necesita antes

- Paso 1 cumplido: está en `/app/platform-api/clientes/` como US.  
- Saber para qué sistema es (aunque sea una prueba: “Postman local”, “ERP nómina”).  
- Un sitio donde guardar el secreto: gestor de contraseñas, variable de entorno, vault. **No** la deje en un chat ni en un ticket.

### Qué hacer

1. En **Clientes de máquina** pulse **+ Nuevo cliente** (o `/app/platform-api/clientes/nuevo/`).  
2. Si duda un campo, use la **Ayuda** de esa pantalla; luego vuelva al formulario.  
3. Complete **Identidad**:

   | Campo | Qué poner en esta primera vez |
   |-------|-------------------------------|
   | **Código** | Obligatorio. Minúsculas, números y guiones, único en la compañía. Ej. `client-prueba-01` |
   | **Uso / nombre** | Opcional. Ej. `Prueba Postman` |
   | **Descripción** | Obligatorio. Sistema, proceso y responsable. Ej. `Prueba local PLATFORM API. Dueño: US de ACME.` |
   | **Entorno** | **Sandbox**. La key empezará por `dw_test_`. No elija Producción hasta tener el flujo estable. |

4. En **Scopes** marque, para este primer circuito (ejecutar + ver resultado + bajar informe):

   | Scope | ¿Marcar ahora? | Para qué |
   |-------|----------------|----------|
   | `jobs:run` | Sí | `POST /api/v1/jobs/run` (kind suelto) |
   | `jobs:read` | Sí | `GET /api/v1/jobs` y `GET /api/v1/jobs/{id}` |
   | `artifacts:download` | Sí | Informe y archivo de salida |
   | `jobs:cancel` | Opcional | Cancelar job en cola / pipeline no terminal |
   | `pipeline:run` | No todavía | Cadena publicada (`kind=file_pipeline`) |

   Los scopes se pueden cambiar después **sin** emitir otra key. La key **no** es un administrador global: no marque todo “por si acaso” en producción; en sandbox de prueba el trío run + read + artifacts basta.

5. Pulse **Crear y mostrar key**.  
6. Llega a **Key emitida** (`…/clientes/{id}/key/`).  
   - Verá el Bearer completo (empieza por `dw_test_`).  
   - Pulse **Copiar** y péguelo en el cofre.  
   - Recuerde el header: `Authorization: Bearer <la-key>`.  
7. Solo cuando esté en el cofre, pulse **Ir al detalle**.

### Qué debe ver después

- Ficha del cliente: código, **Sandbox**, **activo**, pista `…xxxx` (no el secreto).  
- Formularios de configuración y webhook. **No configure el webhook en este paso** (es un aviso al terminar el job; el polling GET basta para el primer circuito).  
- En el listado: 1 activo sandbox.  
- Queda un evento de auditoría de **alta** (lo revisará en un paso posterior).

### Qué no hacer

- No recargue ni cierre **Key emitida** antes de copiar.  
- No ponga la key en el código del repo, capturas de pantalla ni el chat.  
- No cree aún el cliente de **Producción**.  
- No llame a `POST /api/v1/jobs/run` todavía: faltan Contrato/Paths (Paso 3), política (Paso 4) y un proyecto **publicado** (Paso 5). `GET /api/v1/whoami` es el Paso 6.

### Si algo falla

| Qué ocurre | Qué significa |
|------------|----------------|
| Error en Código | Vacío, formato inválido o ya existe ese código en la compañía. Cambie el código. |
| Error en Descripción | Vacía o más de 2000 caracteres. |
| Error en Scopes | Debe marcar **al menos uno**. |
| Solo US puede gestionar clientes | La sesión no es US. |
| Compañía inactiva | No se emite key. |
| Ya no ve la key en pantalla | La revelación de un solo uso caducó o salió de la página. Use **Rotar key** en el detalle (emitirá otra; la anterior deja de servir). |
| Mensaje de que la key ya no está disponible | Igual: rotar, no hay “reenviar por correo”. |

### Listo para el Paso 3 cuando

Tiene un cliente **sandbox activo**, la key `dw_test_…` está en su cofre, y en la ficha ve la **pista** pero no el secreto. Entiende que esa misma key se reutiliza en cada llamada hasta rotarla o revocar el cliente.

---

## Paso 3 — Contrato, Paths e Integración (qué se puede llamar)

### Qué es esto

Tres pantallas US, tres preguntas distintas. **Ninguna ejecuta un job.** No hace falta la key todavía (eso es el Paso 6).

| Pantalla | URL | Pregunta que responde |
|----------|-----|------------------------|
| **Contrato API** | `/app/platform-api/contrato/` | ¿Qué pongo en el body? (`kind`, `wait`, archivos, envelope) |
| **Paths API** | `/app/platform-api/openapi/` | ¿A qué URL pego? (un POST de run, no un path por app) |
| **Integración API** | `/app/platform-api/integracion/` | ¿Este `kind` ya llama al mismo motor que la UI? |

Máquina (más adelante, con Bearer): `GET /api/v1/contract`, `GET /api/v1/openapi`, `GET /api/v1/integration`.

### Qué hacer

#### A. Contrato (`/app/platform-api/contrato/`)

1. Menú **Contrato API** (o el enlace desde Clientes). Abra **Ayuda** si quiere detalle; luego vuelva a la guía.  
2. Lea **Ejes (no mezclar)**:
   - Job suelto: `kind` + `project_slug` (el slug del proyecto en la app).  
   - Cadena: `kind=file_pipeline` + `pipeline_id` (o el atajo de Paths). No mezcle slug de job suelto con id de pipeline.  
   - `wait=sync`: la respuesta llega cuando terminó (HTTP 200). `wait=async`: 202 y luego GET. **Para el primer circuito use sync.** Match, Scout, Clean, Split y Merge **solo** admiten sync.  
3. En la tabla **Kinds** anote, para cada fila:
   - `kind` (el valor que irá en el POST).  
   - **Archivos** (`file`, `file_a`+`file_b`, `files`…).  
   - **Scope** (debe coincidir con lo que marcó en el cliente: job suelto → `jobs:run`; pipeline → `pipeline:run`).  
   - **Ejecutable**: **Sí** = se puede disparar hoy. **Más adelante** = está en el catálogo pero no corre (`file_repair`, `data_profiler` sin app).  
4. Lea **Estados**: `queued` / `running` / `completed` / `failed` / `cancelled`. En Gate, un archivo rechazado puede ser HTTP 200, `ok: false`, `status: completed` y veredicto `rejected` — no es un 400.  
5. En **HTTP de máquina** identifique `POST /api/v1/jobs/validate` (comprueba metadatos **sin** correr el motor). El run es otro path.

**Decisión de este paso:** elija el **primer kind** del circuito. Recomendado: `file_gate` (un archivo `file`, sync, scope `jobs:run`). Anote el `kind` y los nombres de archivo. El **proyecto publicado** es el Paso 5.

#### B. Paths (`/app/platform-api/openapi/`)

1. Menú **Paths API**.  
2. Confirme las reglas: Bearer, `Idempotency-Key` en el run (la usará al ejecutar), un solo POST de ejecución.  
3. En **Superficie HTTP** localice al menos:

   | Uso posterior | Qué buscar en la tabla |
   |---------------|------------------------|
   | Identidad | `GET /api/v1/whoami` |
   | Contrato | `GET /api/v1/contract` |
   | Validar sin ejecutar | `POST /api/v1/jobs/validate` |
   | Ejecutar | `POST /api/v1/jobs/run` |
   | Atajo pipeline | `POST /api/v1/pipelines/{pipeline_id}/runs` (= el mismo run con `kind=file_pipeline`) |
   | Estado | `GET /api/v1/jobs/{job_id}` (un path; el id es el de la app) |
   | Informe / salida | `GET …/report` y `GET …/output` |
   | Listado | `GET /api/v1/jobs` |
   | Cancelar | `POST /api/v1/jobs/{job_id}/cancel` |

4. Si una fila dice **No (MVP)** (p. ej. resumen ops), no la use. El YAML OpenAPI 3 no está publicado: **esta tabla es la lista de rutas**.

No hay `/api/v1/file-gate/run`. El kind va en el cuerpo.

#### C. Integración (`/app/platform-api/integracion/`)

1. Menú **Integración API**.  
2. En **Kinds → runners** busque el `kind` que eligió en A.  
3. **Cableado = Sí** y sin «sin app»: el POST usará el **mismo runner** que el botón Ejecutar de esa app. El `job_id` será el del historial de esa app.  
4. **Cableado = No** o **sin app**: no lo use en el primer circuito (Repair, Profiler).  
5. Lea **UI ↔ API**: ejecutar en la ficha del proyecto ≡ `POST /api/v1/jobs/run` + `kind` + `project_slug`. Watch/Scheduler no son otro motor; cambian `trigger_source`.

### Qué no hacer

- No envíe `POST /api/v1/jobs/run` todavía (Paso 7).  
- No configure webhook.  
- No mezcle Contrato (forma) con Paths (URL) ni con Integración (¿está vivo?).  
- No asuma que «Ejecutable» en Contrato y «Cableado» en Integración son lo mismo: si discrepan, gana **Integración**.

### Si algo falla

| Qué ocurre | Qué significa |
|------------|----------------|
| No ve las tres entradas en el menú | Siga en sesión US (Paso 1). |
| Un kind dice Más adelante / No cableado | Está reservado o la app no está instalada. Elija otro (p. ej. `file_gate`). |
| Confunde `jobs:run` con `pipeline:run` | Job suelto vs cadena. Su cliente del Paso 2 tiene run+read+artifacts, no `pipeline:run`. |

### Listo para el Paso 4 cuando

Ha abierto las tres pantallas. Tiene anotado: **un `kind` cableado** (recomendado `file_gate`), **qué archivo(s)** pide, **`wait=sync`**, y que el disparo es **`POST /api/v1/jobs/run`**. Entiende que falta la política de la compañía y un proyecto **publicado** antes de pegarle al API.

---

---

## Paso 4 — Política de seguridad (límites HTTP de la compañía)

### Qué es esto

La **key** dice *quién* entra. La **política de proceso** dice *qué se acepta* al procesar: tamaño, tipo, cuántas llamadas por minuto, cuánto duran los enlaces de informe/salida y *a qué hosts* puede pegar un webhook.

Es **una política por compañía**, no por cliente. Aplica a todas las keys de esa compañía. El runner de Gate (u otra app) no puede saltársela ([`PLATFORM_API.md`](../PLATFORM_API.md) §4.2 · [`pa_security.md`](pa_security.md)).

Pantalla: **Seguridad API** → `/app/platform-api/seguridad/` (título **Política de proceso**).

### Qué necesita antes

- Pasos 1–3 cumplidos.  
- Sesión US.  
- Para este primer circuito: **no hace falta cambiar los valores**. Abrir, leer y guardar solo si ajusta algo.

### Qué hacer

1. Menú **Seguridad API** (o el botón **Seguridad** desde Clientes). URL:  
   `http://127.0.0.1:8000/app/platform-api/seguridad/`  
2. Si duda un campo, use **Ayuda**; luego vuelva al formulario.  
3. En **Cuotas** compruebe (o deje) los valores por defecto de alta:

   | Campo | Default | Qué implica en el HTTP |
   |-------|---------|------------------------|
   | **Tamaño máximo de archivo (MB)** | `50` (rango 1–500) | Archivo mayor → 400, «El archivo supera el tamaño máximo permitido para esta compañía.» |
   | **Solicitudes por minuto (por key)** | `60` (rango 1–600) | Exceso → 429, «Demasiadas solicitudes. Espere un minuto e intente de nuevo.» (p. ej. `whoami` y run) |
   | **TTL de artifacts (horas)** | `24` (rango 1–168) | Enlace firmado de informe/salida caducado → 404, «El enlace del artifact no es válido o ya expiró.» |
   | **Extensiones permitidas** | `.txt .csv .tsv .xlsx .xls .xml .json` | Tipo ajeno → «Tipo de archivo no permitido. Use los mismos tipos que en la carga de la app.» |

   Las extensiones van separadas por espacio (puede usar coma; el guardado las normaliza con punto).

4. En **Callbacks (anti-SSRF)** deje **Hosts HTTPS permitidos** **vacío** en este circuito (aún no configura webhook). Un host por línea, **sin** `https://`. Solo HTTPS; se rechazan localhost, IPs privadas y userinfo. Lista vacía = ninguna URL de callback pasa. El HMAC y los eventos van en la **ficha del cliente**, no aquí.  
5. Lea la nota fija del formulario: **solo versión publicada**; dry-run no cuenta en el tablero; IDs ajenos → 404 opaco. Eso **no** se desactiva en esta pantalla. Por eso el Paso 5 es publicar el proyecto.  
6. Si no cambió nada, puede salir sin guardar. Si cambió un valor, pulse **Guardar política** y debe ver «Política de proceso API actualizada.»

### Qué no se relaja aquí

| Regla | Comportamiento |
|-------|----------------|
| Solo publicado | Run de proyecto o pipeline no publicado → 409, «Solo se puede ejecutar una versión publicada.» |
| Dry-run y tablero | Un dry-run no suma al pulso de Pipeline. No hay checkbox. |
| IDs ajenos | Job o artifact de otra compañía → 404, «No se encontró el recurso.» |
| Logs | Metadatos y hashes. No cuerpos, celdas, Bearer ni key en claro. |

### Qué no hacer

- No suba el tamaño a 500 «por si acaso» en producción; 50 MB basta para una prueba de Gate.  
- No ponga `localhost` ni `127.0.0.1` en hosts: la validación los rechaza.  
- No configure webhook en el cliente todavía.  
- No llame a `POST /api/v1/jobs/run` todavía (faltan proyecto publicado y `whoami`).  
- No busque un interruptor de «aceptar borradores»: no existe.

### Si algo falla

| Qué ocurre | Qué significa |
|------------|----------------|
| Solo US puede gestionar la política | La sesión no es US. |
| Error en tamaño / rate / TTL | Fuera de rango (MB 1–500, rate 1–600, TTL 1–168). |
| Error en hosts | Host con esquema, mayúsculas raras, o formato inválido. Use `hooks.ejemplo.com`, no `https://hooks.ejemplo.com/path`. |
| Guardó pero el run sigue pidiendo publicado | Correcto: eso no se edita aquí. Paso 5. |
| 429 al probar `whoami` en bucle | El rate está funcionando. Espere un minuto. |

### Listo para el Paso 5 cuando

Ha abierto **Política de proceso**, entiende que es **por compañía**, y que el primer circuito puede usar **50 MB / 60 rpm / 24 h** y las extensiones de intake. Sabe que **sin versión publicada el run será 409**, y que la lista de hosts vacía impide webhooks hasta que la rellene (paso posterior).

---

## Paso 5 — Proyecto publicado y `project_slug`

### Qué es esto

La API **no** lleva el esquema en cada POST. Apunta a un proyecto que **ya existe** en la app y tiene **versión publicada** ([`PLATFORM_API.md`](../PLATFORM_API.md) §3: «MVP = apuntar a proyecto publicado»).

**No es solo File Gate.** Un solo POST (`/api/v1/jobs/run`) sirve a varias apps: el campo `kind` elige el motor; `project_slug` es el **nombre corto de un proyecto de esa misma app**. El código del cliente de máquina (`client-prueba-01`) no va ahí.

| `kind` | App (menú UF) | ¿Cableado hoy? |
|--------|----------------|----------------|
| `file_gate` | File Gate | Sí |
| `dms` | FilePipe | Sí |
| `reverse` | Reverse Studio | Sí |
| `file_match` | File Match | Sí |
| `structure_scout` | Structure Scout | Sí |
| `file_clean` | File Clean | Sí |
| `file_split` / `file_merge` | File Split/Merge | Sí (mismo tipo de proyecto) |
| `file_pipeline` | File Pipeline | Sí, pero usa `pipeline_id`, no `project_slug` (scope `pipeline:run`; no es este primer circuito) |
| `file_repair` / `data_profiler` | — | No (catálogo, sin app) |

Este paso **camina File Gate** porque es el kind recomendado del Paso 3 (un archivo, sync, `jobs:run`). Si ya eligió otro kind **cableado**, publique en **esa** app y anote **su** slug; no mezcle (un slug de FilePipe con `kind=file_gate` es 400). El inventario vivo está en **Integración API** (Paso 3).

### Qué necesita antes

- Pasos 1–4. El cliente API y el proyecto deben ser de la **misma compañía**.  
- Acceso al menú de operaciones (**File Gate** está en la barra **UF**, no en la de US). Si usted solo es US, use un usuario UF de la misma compañía que pueda crear o administrar el proyecto, o pida a quien ya tenga un Gate publicado el slug.  
- Un archivo de prueba cuya extensión esté en la política del Paso 4 (p. ej. `.csv`).

Si **ya tiene** un File Gate con contrato publicado en esa compañía, no cree otro: anote el slug y salte a «Qué debe anotar».

### Qué hacer (File Gate)

1. En el menú de operaciones pulse **File Gate** → listado  
   `http://127.0.0.1:8000/app/file-gate/proyectos/`  
   No confunda esta lista con **Clientes de máquina**.

2. **Si crea uno nuevo:** **Nuevo proyecto** (`…/proyectos/nuevo/`).

   | Campo | Qué poner |
   |-------|-----------|
   | **Nombre corto (código)** | Obligatorio. Único en la organización. **Este texto es el `project_slug`.** Ej. `gate-prueba-api` |
   | **Nombre visible** | Ej. `Prueba API File Gate` |
   | **Descripción / visibilidad** | Según la ayuda de esa pantalla. No cambia el slug. |

   Tras crear, la ficha muestra el slug en la insignia y en la URL:  
   `/app/file-gate/proyectos/<project_slug>/`

3. En el hub del proyecto complete **Contrato de validación** (asistente de **6 pasos**) y las **políticas**. Use **Ayuda** de File Gate si es la primera vez; este manual no sustituye ese diseño. Para una prueba rápida: tipo de archivo **CSV** (coincide con las extensiones default de la API).

4. En el hub del esquema, cuando los 6 pasos estén completos, pulse **Publicar contrato vN**. Debe quedar una versión **publicada** (el hub del proyecto: «Suba un archivo… contra la versión publicada», no «Publique el contrato para habilitar…»). Publicar congela esquema + política; Validar y la API usan esa versión, no el borrador.

5. **Opcional y recomendable:** **Ir a validar**, suba el CSV de prueba y confirme que la UI corre. Es el **mismo runner** que usará `POST /api/v1/jobs/run`. Si falla en UI, fallará igual por API.

6. Anote en un papel (junto al kind del Paso 3):

   | Dato | Ejemplo |
   |------|---------|
   | `kind` | `file_gate` |
   | `project_slug` | `gate-prueba-api` (el código, no el nombre visible) |
   | Archivo | un campo `file`, p. ej. CSV |
   | `wait` | `sync` |

El `kind` debe coincidir con el tipo de proyecto: un slug de FilePipe / Match / etc. con `kind=file_gate` será 400 (kind y proyecto no coinciden). Un slug que no exista o esté archivado: 404 opaco.

### Qué no hacer

- No envíe aún `POST /api/v1/jobs/run` ni `whoami` (Pasos 6–7).  
- No use el código del **cliente API** como `project_slug`.  
- No dispare un **borrador**: la política del Paso 4 exige publicado → 409 «Solo se puede ejecutar una versión publicada.»  
- No arme un pipeline en este circuito (`pipeline:run` no está en la key del Paso 2).  
- No archive el proyecto.

### Si algo falla

| Qué ocurre | Qué significa |
|------------|----------------|
| No ve File Gate en el menú | Está en sesión US. Entre con UF de la misma compañía (o quien diseña Gate). |
| No puede publicar | Faltan pasos del contrato (6/6) o no es administrador del proyecto. |
| Validar en UI dice que publique primero | Aún no hay versión publicada. |
| El slug ya existe | El código es único en la organización. Elija otro o reutilice ese proyecto si es Gate y está publicado. |
| Creó el proyecto en otra compañía | La key del Paso 2 no lo verá (404). |

### Listo para el Paso 6 cuando

Tiene un File Gate (u otro kind elegido) **con versión publicada** en la **misma compañía** que el cliente sandbox, y anotó el **`project_slug`** (nombre corto). Idealmente ya validó un archivo en la UI.

---

## Paso 6 — Primera llamada HTTP: `whoami` y validar

### Qué es esto

Hasta ahora todo era consola web. Ahora el **cliente de máquina** habla HTTP con Bearer (la key del Paso 2). Dos llamadas, **sin ejecutar** el motor de Gate:

| Orden | Path | Para qué |
|-------|------|----------|
| 1 | `GET /api/v1/whoami` | ¿La key sirve? ¿compañía, entorno, scopes, política? |
| 2 | `POST /api/v1/jobs/validate` | ¿El body (`kind`, `project_slug`, `wait`) es válido y el cliente tiene el scope? |

`validate` **no** comprueba que el proyecto exista ni que esté publicado, **ni** corre el runner. Eso es el Paso 7 (`POST /api/v1/jobs/run`). Si `validate` responde 200 con `executed: false`, solo ganó la forma del request.

Opcional: `GET /api/v1/contract` es el mismo catálogo que la pantalla Contrato, en JSON.

Base local: `http://127.0.0.1:8000`. En Windows PowerShell use **`curl.exe`**. La misma llamada en **Postman** está en cada apartado, **pendiente** hasta que la confirme ([preparación](#postman--misma-api-que-curl-pendiente)).

### Qué necesita antes

- Key sandbox en el cofre (`dw_test_…`). No la pegue en chats ni en este archivo.  
- `kind` y `project_slug` del Paso 5.  
- El servidor Django en marcha.

### Qué hacer

#### A. Identidad — `GET /api/v1/whoami`

**El header es siempre el mismo.** El nombre `Authorization` y la palabra `Bearer` no cambian al crear el cliente ni al rotar. Cada llamada autenticada lleva:

```text
Authorization: Bearer <la-key-actual>
```

| Parte | ¿Cambia al crear o rotar? |
|-------|---------------------------|
| Nombre del header: `Authorization` | No. Es el estándar HTTP. |
| Esquema: `Bearer` | No. Siempre esa palabra, **un espacio**, y luego la key. |
| La key (`dw_test_…` o `dw_live_…`) | **Sí.** Al crear o al **Rotar key** sale un secreto nuevo; el anterior deja de servir. |

Los puntos suspensivos de la pantalla de la key («Bearer …») solo significan “aquí va la key”. **No los escriba.** Tampoco escriba los signos `<` `>`: en este manual marcan un hueco, no forman parte del valor.

Misma key en **todas** las rutas (`whoami`, `validate`, `run`, GET job, etc.) hasta que rote o revoque. Rotar no cambia el header: cambia **solo** el texto que va después de `Bearer`. Sandbox y producción son **dos clientes**, cada uno con su key; el header sigue siendo `Authorization: Bearer …`.

Péguela desde el cofre del Paso 2 (sandbox empieza por `dw_test_`). Si ya no la tiene en claro, **Rotar key** en la ficha y use la nueva.

```text
curl.exe -sS -H "Authorization: Bearer dw_test_…" http://127.0.0.1:8000/api/v1/whoami
```

Sustituya `dw_test_…` por la key completa, **sin** ángulos ni puntos suspensivos.

**Postman (hecho).** Sin Header a mano y sin Body. Auth Bearer Token (key sola). `GET` whoami → HTTP **200**. Cuerpo real de esta prueba:

```json
{
    "ok": true,
    "client_code": "api-qa-p01",
    "environment": "sandbox",
    "company": "ACME",
    "scopes": [
        "jobs:run",
        "jobs:read",
        "jobs:cancel",
        "pipeline:run",
        "artifacts:download"
    ],
    "process_policy": {
        "max_upload_bytes": 52428800,
        "rate_per_minute": 60,
        "artifact_ttl_hours": 24,
        "require_published": true
    }
}
```

El Environment y el Bearer están bien. **6 A cerrado.** Siga en **#### B** (otro request: **POST** `…/jobs/validate`, **no** este GET).

No hace falta un scope especial para `whoami`: basta un Bearer válido. Cada llamada cuenta en el rate (si dispara en bucle, 429).

#### B. Metadatos — `POST /api/v1/jobs/validate`

Sustituya el slug por el del Paso 5. **No adjunte archivo** todavía (si no hay files, no se exigen). En PowerShell o cmd:

```text
curl.exe -sS -X POST -H "Authorization: Bearer dw_test_…" -F "kind=file_gate" -F "project_slug=gate-prueba-api" -F "wait=sync" http://127.0.0.1:8000/api/v1/jobs/validate
```

Mismo header que en A: `Authorization` y `Bearer` fijos; solo cambia la key. Sustituya `dw_test_…` y el slug.

**Postman (hecho).** Request **nuevo** (POST, no el GET de whoami). URL `{{base}}/api/v1/jobs/validate`. Mismo Bearer. Body **form-data** (tres filas Text, sin `file`):

| KEY | TYPE | VALUE |
|-----|------|--------|
| `kind` | Text | `file_split` |
| `project_slug` | Text | `prueba-02-txtd` |
| `wait` | Text | `sync` |

Datos de la prueba (Postman: POST, form-data, Auth Bearer). HTTP **200**. Cuerpo real:

```json
{
    "ok": true,
    "user_message": "Metadatos del contrato válidos. Este endpoint no ejecuta el job.",
    "validated": true,
    "executed": false,
    "request": {
        "kind": "file_split",
        "wait": "sync",
        "version": "published",
        "project_slug": "prueba-02-txtd",
        "pipeline_id": null,
        "dry_run": false,
        "retry_of_job_id": null,
        "idempotency_key": "",
        "correlation_id": "",
        "client_ip": "127.0.0.1",
        "user_agent": "PostmanRuntime/7.56.1",
        "files_required": ["file"],
        "multi_file": false,
        "scope": "jobs:run",
        "default_http_status": 200
    }
}
```

`executed: false` = no corrió el Split. `files_required: ["file"]` avisa qué pedirá el **run** (Paso 7). `user_agent` Postman es esperado.

**Primer intento (cerrado):** 400 si se reutilizaba whoami (GET / Body none). El POST con la tabla de arriba es el 200.

Siguiente: **6 C** (opcional) o **Paso 7**. **6 C Postman ya está hecho** si sigue este documento en orden.

#### C. Opcional — `GET /api/v1/contract`

Mismo Bearer. Debe listar `kinds` (entre ellos `file_gate` y `file_split`). Sirve para cruzar con la pantalla Contrato.

**Postman (hecho).** GET `http://127.0.0.1:8000/api/v1/contract` (no `jcontract`). Mismo Bearer. Body none. HTTP **200** JSON (`ok: true`, `client_code`: `api-qa-p01`).

**Primer intento (cerrado):** HTML 404 en `…/jcontract`.

En esta prueba el catálogo trae `wait` (sync/async), `job_status`, `gate_verdict`, `step_status`, `kinds` (Gate, FilePipe, Reverse, Match, Scout, Clean, **File Split** `file_split` + `files: ["file"]`, Merge, Repair y Profiler con `mvp_phase_a: false`, Pipeline con scope `pipeline:run`), `envelope_fields`, `paths` (`run`, `job`, `report`, `output`, `validate`, `whoami`, …). Cruza con la pantalla Contrato US. `file_split` del 6 B está en `kinds`.

Siguiente: **Paso 7** (POST run + archivo).

### Qué no hacer

- No llame a `POST /api/v1/jobs/run` todavía (Paso 7).  
- No use cookie de sesión US/UF en lugar del Bearer.  
- No ponga `Authorization: Bearer` sin la key, ni la key en query string.  
- No dispare `whoami` en un bucle para “probar el rate” ahora: se bloquea un minuto.  
- No interprete un 200 de `validate` como “el proyecto está publicado”.

### Si algo falla

| Qué ocurre | Qué significa |
|------------|----------------|
| 401 · `invalid_token` · «Credencial ausente o inválida.» | Header mal, key recortada, cliente revocado, o ya rotó y usa la key vieja. **Si copió el marcador** (`<dw_test_…>` o un texto de ejemplo) en lugar de la key del cofre, también es 401. |
| 403 · `company_inactive` | La compañía no está activa. |
| 403 · `insufficient_scope` en validate | El `kind` pide un scope que la key no tiene (p. ej. `file_pipeline` → `pipeline:run`). |
| 400 · `kind` «Kind no reconocido.» | En Postman: request de whoami (GET / Body none) o Body vacío. 6 B es **POST** `…/validate` con las tres filas form-data. |
| 400 · falta `project_slug` | Job suelto exige slug (o `project_id`). |
| 400 · mezcla slug y `pipeline_id` | Un eje u otro, no los dos. |
| 429 · `rate_limited` | Superó solicitudes/minuto de la política. Espere un minuto. |
| `curl` de PowerShell extraño | Use `curl.exe`. |
| HTML 404 · URL `…/jcontract` | Typo en Postman. El path es `/api/v1/contract`. |

### Listo para el Paso 7 cuando

**Paso 6 Postman (A–C) cerrado.** Siguiente: **Paso 7** en Postman (`POST /jobs/run` + File).

---

## Paso 7 — Ejecutar un job (`POST /api/v1/jobs/run`)

### Qué es esto

Esta llamada **sí corre el motor**: el mismo runner que **Ir a validar** en File Gate (u otra app según `kind`). Scope: `jobs:run`.

Primer circuito: `kind=file_gate`, `wait=sync`, un archivo en el campo **`file`**, versión publicada. HTTP **200** cuando el job **terminó** (aunque Gate **rechace** el archivo: eso es negocio, no un 400).

### Qué necesita antes

- Pasos 1–6 (key que ya autenticó en `whoami`).  
- `project_slug` publicado.  
- Un archivo de prueba **en disco** cuya extensión esté en la política (p. ej. `.csv`) y que coincida con el tipo del contrato Gate.  
- Un valor **nuevo** de `Idempotency-Key` (texto suyo, p. ej. `prueba-gate-001`). Mismo key + mismo archivo + mismos metadatos = **no reejecuta**, devuelve el mismo `job_id`. Para forzar otra corrida, cambie la Idempotency-Key.

Header fijo: `Authorization: Bearer` + espacio + la key (`dw_test_…`), sin `< >` ni «…».

### Qué hacer

En PowerShell, ponga la ruta real del CSV (el `@` delante del path es de curl: “leer este archivo”). Sustituya slug, key e Idempotency-Key:

```text
curl.exe -sS -X POST -H "Authorization: Bearer dw_test_…" -H "Idempotency-Key: prueba-gate-001" -F "kind=file_gate" -F "project_slug=gate-prueba-api" -F "wait=sync" -F "file=@C:\ruta\prueba.csv" http://127.0.0.1:8000/api/v1/jobs/run
```

| Pieza del comando | Valor que corresponde |
|-------------------|------------------------|
| `curl.exe` | Cliente HTTP de Windows. No use el alias `curl` de PowerShell. |
| `-sS` | Silencioso pero muestra errores de red. |
| `-X POST` | Método HTTP. El run **siempre** es POST. |
| `-H "Authorization: Bearer dw_test_…"` | Header fijo: nombre `Authorization`, palabra `Bearer`, un espacio y **su** key del cofre. Sustituya `dw_test_…` por la key completa. No escriba `< >` ni los puntos. En producción el prefijo sería `dw_live_`. |
| `-H "Idempotency-Key: prueba-gate-001"` | Identificador **suyo** de este lote. Ejemplo del comando: `prueba-gate-001`. Cámbielo en cada corrida **distinta**. Mismo valor + mismo archivo + mismos campos = no reejecuta. |
| `-F "kind=file_gate"` | App a ejecutar. Este circuito: `file_gate`. Otros kinds: ver Paso 3 / Integración. |
| `-F "project_slug=gate-prueba-api"` | Nombre corto del proyecto **publicado** (Paso 5). Sustituya el ejemplo `gate-prueba-api` por el suyo. |
| `-F "wait=sync"` | Esperar el resultado en esta respuesta (HTTP 200). Primer circuito: déjelo en `sync`. |
| `-F "file=@C:\ruta\prueba.csv"` | Archivo de entrada. El nombre del campo es `file`. El `@` indica a curl que lea el path. Sustituya `C:\ruta\prueba.csv` por un archivo real (extensión permitida, p. ej. `.csv`). |
| URL `http://127.0.0.1:8000/api/v1/jobs/run` | Path único de ejecución. El `kind` no va en la URL. En otro entorno cambie solo el host. |
| (no está en el ejemplo) `version` | Si no lo envía, se asume `published`. |
| (no está en el ejemplo) `Content-Type: application/json` | **No** lo use aquí. `-F` ya manda `multipart/form-data`, que es lo que lleva el archivo. |

**Postman (pendiente).** **Request nuevo** (no es validate). Esta llamada **sí ejecuta** (o hace replay si la Idempotency-Key y el archivo coinciden con el curl).

| Postman | Valor |
|---------|--------|
| Method | **POST** |
| URL | `http://127.0.0.1:8000/api/v1/jobs/run` o `{{base}}/api/v1/jobs/run` |
| Authorization | Type **Bearer Token**. Token = `{{key}}` (solo la key, **sin** `Bearer`). No cree Header `Authorization` a mano |
| Headers (pestaña **Headers**) | **Sí, uno extra:** KEY `Idempotency-Key` · VALUE p. ej. `prueba-post-001` (la del curl de esta prueba = **replay**, mismo `job_id`). Otra cadena = **otro job** |
| Body | **form-data** (no raw JSON, no none, no x-www-form-urlencoded) |

**Body → form-data** (cuatro filas; la última es File):

| KEY | TYPE | VALUE |
|-----|------|--------|
| `kind` | Text | `file_split` |
| `project_slug` | Text | `prueba-02-txtd` |
| `wait` | Text | `sync` |
| `file` | **File** (el desplegable de la fila, no Text) | el `.txt` de disco (p. ej. `concilia01b.txt`) |

No ponga `Content-Type` a mano. No use Body JSON. Sin fila `file` → 400 falta archivo.

Send. En Split sync: HTTP **200**.

**Postman (hecho).** POST `…/jobs/run`, Bearer, header `Idempotency-Key: prueba-post-001`, form-data `kind`/`project_slug`/`wait` + File `concilia01b.txt`. HTTP **200**. Mismo `job_id` que curl (`481ee7ff-e129-4525-82a3-d3608237d6ca`): **replay**, no una segunda partición. `user_message`: «Partición File Split finalizada.» `kind`/`project_slug`/`status` = `file_split` / `prueba-02-txtd` / `completed`. `artifacts.report_url` presente; **sin** `output_url`. `audit.idempotency_key`: `prueba-post-001`. `audit.user_agent` sigue `curl/8.21.0` (cuerpo guardado del primer run, no PostmanRuntime).

Siguiente: **Paso 8 A** (GET detalle, Body none).

### Qué debe ver (sync + Gate)

HTTP **200**. Cuerpo tipo envelope. Anote el **`job_id`** (UUID); lo usará en el Paso 8.

| Campo | Qué mirar |
|-------|-----------|
| `ok` | `true` si Gate aceptó. `false` si el contrato rechazó el archivo (**sigue siendo 200** y `status` suele ser `completed`). |
| `status` | Estado de máquina: `completed` / `failed` / … **No** use `accepted` como status: en Gate el veredicto va en `summary.verdict` (`accepted` \| `rejected`). |
| `kind` / `project_slug` | `file_gate` y su slug. |
| `user_message` | «Validación Gate finalizada.» |
| `job_id` | El mismo id que verá en el historial de File Gate. |
| `summary.verdict` | `accepted` o `rejected`. |
| `artifacts.report_url` | Ruta tipo `/api/v1/jobs/{job_id}/report` (bajarla es el Paso 8). `output_url` en Gate suele ir vacío: Gate no genera archivo de negocio. |
| `links.self` | `GET` del job. |
| `audit.trigger_source` | `api`. |

Si **repite el mismo** `Idempotency-Key` con el **mismo** archivo y campos: 200 otra vez, mismo `job_id`, mensaje de respuesta reutilizada. Si reutiliza la key con **otro** archivo: 409 «Idempotency-Key ya usada con otra entrada. Use una key nueva.»

### Qué no hacer

- No ponga `wait=async` en este primer circuito (202 + cola; el detalle es Paso 8).  
- No mezcle `pipeline_id` ni `kind=file_pipeline` (su key del Paso 2 no tiene `pipeline:run`).  
- No reenvíe el run en bucle con keys de idempotencia nuevas “por si acaso”: cada una **ejecuta** de verdad.  
- No baje aún report/output (Paso 8).  
- No use cookie de sesión en lugar del Bearer.

### Si algo falla

| Qué ocurre | Qué significa |
|------------|----------------|
| 401 | Key mal puesta (mismos consejos del Paso 6). |
| 403 `insufficient_scope` | El cliente no tiene `jobs:run`. |
| 400 archivo / tipo / tamaño | Política del Paso 4 o falta el campo `file`. |
| 404 «No se encontró el recurso.» | Slug inexistente, archivado u otra compañía (respuesta opaca). |
| 409 «Solo se puede ejecutar una versión publicada.» | El proyecto no tiene versión publicada (Paso 5). |
| 400 kind vs proyecto | El slug no es un proyecto File Gate (u otro kind cruzado). |
| 409 idempotencia | Misma Idempotency-Key, distinta entrada. Cambie el header. |
| 429 | Rate de la política. Espere un minuto. |
| 200 + `ok: false` + `verdict: rejected` | El job **sí corrió**. El archivo no cumple el contrato. Eso no es un fallo del POST. |

### Listo para el Paso 8 cuando

Tiene un **200** de `jobs/run` en **curl** y en **Postman** (mismo `job_id` por idempotencia). Entiende que `ok` no es el código HTTP. **Paso 8 Postman** sigue **pendiente**.

---

## Paso 8 — Consultar estado, informe y salida

### Qué es esto

El `POST /jobs/run` ya corrió. Ahora **lee**. No se vuelve a ejecutar el motor. Las cuatro llamadas usan el **mismo** Bearer; A y D el **mismo** `job_id` del Paso 7 (salvo D, que no lleva UUID en la URL). El `job_id` es el de la **app** (historial Split, Gate, etc.), no un id paralelo.

Ninguna de las cuatro **dispara** trabajo. Se distinguen por **qué pregunta hacen** y **qué cuerpo devuelven**.

### Las cuatro consultas (A–D)

Haga **A primero**. Según lo que traiga `artifacts`, decida B y C. D es opcional (visión de compañía).

| | A. Detalle | B. Informe | C. Salida | D. Listado |
|--|------------|------------|-----------|------------|
| **Qué es** | Ficha JSON de **un** job | Archivo de **evidencia / manifiesto** de ese job | Archivo de **negocio** de ese job (el que saldría hacia el ERP) | Página JSON de **varios** jobs de la compañía |
| **Path** | `GET /api/v1/jobs/{job_id}` | `GET …/jobs/{job_id}/report` | `GET …/jobs/{job_id}/output` | `GET /api/v1/jobs?kind=…&limit=…` |
| **Scope** | `jobs:read` | `artifacts:download` (o `?token=` del detalle) | Igual que B | `jobs:read` |
| **Cuerpo** | Envelope: `ok`, `status`, `summary`, `artifacts`, `audit` | Bytes (en Split: JSON de partes, no el envelope) | Bytes (CSV, TXT, ZIP…) **o** 404 JSON | `{ jobs, total, limit, offset }` |
| **Para qué** | ¿Terminó? ¿`kind`? ¿Hay `report_url` / `output_url`? Correlación con el run | Auditoría, conteo de partes, hashes, veredicto Gate, change log Clean | Tomar el fichero transformado / unido / generado | Operaciones, “¿ya existe este job?”, filtros sin saber el UUID |
| **No es** | Ni el manifiesto ni el `.txt` de salida | Ni las 4 partes del Split ni el envelope de A | Ni el manifiesto. No empaqueta N archivos en un ZIP | Ni el detalle profundo de uno solo (aunque cada ítem copie el shape de A) |

**Diferencias que importan en esta prueba (Split):**

1. **A vs B.** A dice *que* hay informe (`report_url`). B *es* ese informe. A se lee en la terminal. B se guarda en un archivo (`informe2.bin`). Si B empieza por `"ok": false`, no es el manifiesto.
2. **B vs C.** B = índice (`operation`, `parts[]`, nombres). C = un solo fichero de negocio. Con varias partes, C **no existe**: 404 «El artifact no está disponible.» Aunque B haya sido 200. Mire `output_url` en A: si falta, no llame C.
3. **A vs D.** A = un UUID. D = la compañía (`kind=file_split` trajo 6 ítems: el de API y otros de la UI). D no sustituye a A para decidir C; sirve para encontrar `job_id` o ver el pulso.
4. **C no se “arregla”** con otra key, otro `.bin` o un pipeline publicado. Se resuelve **por job**. Gate y Scout tampoco suelen tener C; Clean / DMS / Merge a un archivo sí.

Job ajeno o inventado en A/B/C: **404** opaco («No se encontró el recurso.»), distinto del 404 de C cuando el job **sí** existe pero no hay un output único.

### Qué necesita antes

- Un `job_id` de un run **200** (Paso 7). Ejemplo de forma: `481ee7ff-e129-4525-82a3-d3608237d6ca` (use el suyo).  
- La misma key Bearer. Scopes `jobs:read` y `artifacts:download` (Paso 2).

### Qué hacer

Sustituya `dw_test_…` por la key y el marcador `{job_id}` por el UUID **sin llaves** (en PowerShell `{…}` es un bloque de script y curl puede pedir contraseña). Ejemplo de URL: `http://127.0.0.1:8000/api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca`. Header: `Authorization: Bearer` + key, sin `< >`.

#### A. Detalle

`GET` es el **método HTTP**, no un comando de PowerShell. Si escribe `GET /api/v1/jobs/…` en la terminal, falla: `GET : The term 'GET' is not recognized`. Use **`curl.exe`**. La URL va entre comillas.

```text
curl.exe -sS -H "Authorization: Bearer dw_test_…" "http://127.0.0.1:8000/api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca"
```

**Postman (hecho).** GET detalle, Bearer `{{key}}`, Body none. HTTP **200**. `ok: true`, `user_message`: «Job encontrado.», mismo `job_id` `481ee7ff-…`, `kind`/`project_slug`/`status` = `file_split` / `prueba-02-txtd` / `completed`. `artifacts.report_url` con `?token=` y `report_ttl_seconds`: `86400`. **Sin** `output_url`. `audit.idempotency_key`: `prueba-post-001`. No copie el token a un chat. **8 B–D** ya están hechos. Siguiente: **Paso 10** (Postman).

| KEY | TYPE | VALUE |
|-----|------|--------|
| Method | — | `GET` |
| URL | — | `{{base}}/api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca` |
| Authorization | Bearer Token | `{{key}}` (key sola, sin la palabra `Bearer`) |
| Headers | — | ninguno extra (no cree `Authorization` a mano) |
| Body | none | — |

| Pieza del comando | Valor que corresponde |
|-------------------|------------------------|
| `curl.exe` | Cliente HTTP de Windows. No use el alias `curl` de PowerShell. No escriba la palabra `GET`. |
| `-sS` | Silencioso pero muestra errores de red. |
| (no hay `-X`) | curl usa GET si no pone `-X`. **No** ponga `-X POST`: esto solo consulta. |
| `-H "Authorization: Bearer dw_test_…"` | Igual que el Paso 6/7: `Authorization`, `Bearer`, un espacio y **su** key. Sustituya `dw_test_…`. Sin `< >` ni puntos suspensivos. |
| URL `…/api/v1/jobs/{job_id}` | El UUID va **en la URL**, no en `-F`. `{job_id}` es marcador: péguelo **sin** `{` `}`. Mal: `…/jobs/{481ee7ff-…}`. Bien: `…/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca`. |
| Respuesta | JSON. `user_message`: «Job encontrado.» Mismos `status`, `kind`, `summary` que el run. |

Tras un Split sync, debe ver el mismo `kind` (`file_split`), `status: completed`, `summary.operation: split`, `files_out`, etc.

HTTP **200**. Ejemplo real de esta prueba (`kind=file_split`, proyecto `prueba-02-txtd`). Sus UUID y token serán otros; el **shape** es el mismo.

| Campo | Qué esperar / ejemplo |
|-------|------------------------|
| `ok` | `true` si el job se resolvió y la operación no falló a nivel máquina. |
| `job_id` | Mismo UUID que en el run. Ej. `481ee7ff-e129-4525-82a3-d3608237d6ca`. |
| `kind` | `file_split` (el del POST). |
| `project_slug` | Slug del proyecto. Ej. `prueba-02-txtd`. |
| `pipeline_id` | `null` en job suelto (no es cadena). |
| `version` | Versión publicada usada. Ej. `v1`. |
| `wait` | El del run. Ej. `sync`. |
| `status` | Estado de máquina. Ej. `completed`. |
| `summary.operation` | En Split/Merge: `split` o `merge`. |
| `summary.dry_run` | `false` si fue ejecución real. |
| `summary.files_in` | Archivos de entrada. Ej. `1`. |
| `summary.files_out` | Partes generadas. Ej. `6`. |
| `summary.rows_read` | Filas leídas. Ej. `49`. |
| `errors` | Lista vacía `[]` si no hay errores tipados. |
| `artifacts.report_url` | Ruta `/api/v1/jobs/{job_id}/report` **con** `?token=…` (firma + TTL). Sirve para bajar el manifiesto **sin** Bearer hasta que caduque. No copie el token a un chat. En el **run** a veces viene sin token; en el **GET detalle** suele ir firmada. |
| `artifacts.report_ttl_seconds` | Segundos de vida del enlace. Ej. `86400` (24 h, política del Paso 4). |
| `artifacts.output_url` | Ausente si no hay un solo archivo de salida (este Split). |
| `content_hash` | SHA del contenido de entrada. Debe coincidir con el del run. |
| `links.self` | `GET` de este mismo job: `/api/v1/jobs/{job_id}`. |
| `audit.trigger_source` | `api`. |
| `audit.api_client_id` | Cliente de máquina que disparó. |
| `audit.idempotency_key` | La del run. Ej. `prueba-post-001`. |
| `audit.correlation_id` | Traza de la petición. |
| `audit.duration_ms` | Duración. Ej. `18`. |
| `audit.input_filename` / `input_size_bytes` | Metadatos de intake; en esta prueba pueden ir vacíos (`""` / `0`). |
| `user_message` | En el GET: «Job encontrado.» (en el POST run era «Partición File Split finalizada.»). |

#### B. Informe

> **Probado.** Con un cliente que tiene `artifacts:download`, el cuerpo **no** es un `error_code`: es el manifiesto Split. En PowerShell, `--output` y URL entre comillas evitan el choque con `-o` (igual que en C). `-o informe2.bin` también funcionó aquí porque el path termina en `/report`, no en `/output`.

```text
curl.exe -sS -L -H "Authorization: Bearer dw_test_…" --output informe2.bin "http://127.0.0.1:8000/api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca/report"
```

**Postman (hecho).** Request **nuevo** (`/report`, no el detalle). GET, Bearer `{{key}}`, Body none. URL **sin** `/j/` (`…/api/v1/jobs/481ee7ff-…/report`). HTTP **200**. Cuerpo = manifiesto (no envelope `ok`/`job_id`): `operation` `split`, `parts_count` `4`, `rows_read` `49`, `partition_code` `max_rows`, cuatro `parts` (`part_001`…`004`, `concilia01b_part_00N.txt`, filas 15/15/15/4, `size_bytes` 1320/1320/1320/352). Igual que `informe2.bin` de curl. Save Response → archivo es opcional. **Primer intento:** HTML 404 en `/j/api/v1/…` — no es el informe.

| KEY | TYPE | VALUE |
|-----|------|--------|
| Method | — | `GET` |
| URL | — | `http://127.0.0.1:8000/api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca/report` |
| Authorization | Bearer Token | `{{key}}` |
| Headers | — | ninguno extra |
| Body | none | — |

La URL **no** lleva `/j/` entre el host y `api`. Mal: `…/j/api/v1/jobs/…/report`. Bien: `…/api/v1/jobs/…/report`.

**Primer intento (no cerrado):** HTML 404 *Page not found at `/j/api/v1/jobs/…/report`*. Eso no es el manifiesto: Django no tiene esa ruta. Quítele `/j`. Un 200 correcto es JSON que empieza por `"operation": "split"`, no HTML.

**8 C** (hecho): GET `…/output` → 404 JSON. **8 D** hecho.

| Pieza del comando | Valor que corresponde |
|-------------------|------------------------|
| `curl.exe` | Igual que en A. |
| `-sS` | Igual que en A. |
| `-L` | Sigue redirecciones si el servidor las envía al adjunto. |
| `-H "Authorization: Bearer dw_test_…"` | Mismo Bearer. Scope necesario: `artifacts:download` (con solo `jobs:read` el detalle va; los **bytes** no). |
| `--output informe2.bin` | Guarda el cuerpo en ese archivo local. El nombre real lo manda el servidor (`Content-Disposition`). Cambie el nombre si quiere otra ruta. |
| URL `…/jobs/{job_id}/report` | Mismo UUID que en A, **sin llaves**, más el sufijo `/report`. Entre **comillas**. |
| (alternativa) `?token=` | Si el envelope trae `report_url` con `token`, esa URL puede ir **sin** Bearer hasta el TTL del Paso 4. |

El cuerpo queda en el directorio desde el que corrió curl. **No** es el envelope del GET detalle (no tiene `ok` / `job_id` / `user_message`).

**Lo que salió en esta prueba** (`informe2.bin`): HTTP **200**. Empieza por `"operation": "split"` — es el manifiesto, no un error. Campos reales:

| Campo | Valor en esta prueba |
|-------|----------------------|
| `operation` | `split` |
| `parts_count` | `4` |
| `rows_read` | `49` (suma de `parts[].rows`: 15+15+15+4) |
| `partition_code` | `max_rows` |
| `parts` | Lista de 4 objetos |

Cada ítem de `parts` (forma; hashes y tamaños serán otros si cambia el archivo):

| Campo | Ejemplo (`part_001`) |
|-------|----------------------|
| `part_key` | `part_001` … `part_004` |
| `filename` | `concilia01b_part_001.txt` |
| `rows` | `15` (la última parte: `4`) |
| `label` | `Filas 1-15` |
| `size_bytes` | `1320` (última: `352`) |
| `content_hash` | SHA del contenido de esa parte |

Esto **no** son los `.txt` de negocio: es el índice. Las partes se ven en el historial UF de File Split/Merge. `GET …/output` sigue en 404 (no hay un solo archivo).

Si reutiliza la misma `Idempotency-Key` (`prueba-post-001`), el POST y el GET detalle pueden seguir mostrando `summary.files_out: 6` del **primer** run. El manifiesto es lo que hay ahora en disco (`parts_count: 4`). Para contar partes, use el report, no el summary cacheado.

**Si el archivo es un error** (p. ej. un `informe.bin` viejo): empieza por `"ok": false`. `insufficient_scope` = falta `artifacts:download` (Paso 10). No mezcle ese archivo con el manifiesto.

#### C. Salida (solo si hay `output_url`)

> **Probado en curl y Postman — 404 correcto.** El report **sí** baja; el output **no**. Un pipeline publicado **no** cambia este UUID.

El comando (solo cuando el detalle **sí** liste `output_url`):

```text
curl.exe -sS -L -H "Authorization: Bearer dw_test_…" --output salida3.bin "http://127.0.0.1:8000/api/v1/jobs/{job_id}/output"
```

**Postman (hecho).** Request **nuevo** (`/output`). GET, Bearer `{{key}}`, Body none, URL sin `/j/`. HTTP **404**. Mismo JSON que curl (`ok: false`, `error_code`: `not_found`, `user_message`: «El artifact no está disponible.», `errors`: `[]`). No es un Bearer mal puesto: el job existe (8 A/B 200) y no hay un solo archivo de salida. El texto «Requested resource could not be found» de Postman es el status 404, no otra ruta HTML.

| KEY | TYPE | VALUE |
|-----|------|--------|
| Method | — | `GET` |
| URL | — | `{{base}}/api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca/output` |
| Authorization | Bearer Token | `{{key}}` |
| Headers | — | ninguno extra |
| Body | none | — |

**8 D** (hecho): GET `/api/v1/jobs`.

**Lo que salió** (`salida.bin`, `salida2.bin`, `salida3.bin` — mismo JSON): HTTP **404**.

| Campo | Valor |
|-------|--------|
| `ok` | `false` |
| `error_code` | `not_found` |
| `user_message` | «El artifact no está disponible.» |
| `errors` | `[]` |

No es un fallo de Bearer ni de PowerShell. La API no empaqueta las 4 partes del manifiesto en un ZIP. Las partes están en el historial UF de File Split/Merge. Un kind con un solo archivo (Clean, DMS, Merge) sí devolvería 200 aquí.

#### D. Opcional — listado

> **Probado.** Comillas en la URL (el `&` de PowerShell). Scope `jobs:read`. HTTP **200**. No hace falta `artifacts:download`: esto es JSON en la terminal, no un `.bin`.

```text
curl.exe -sS -H "Authorization: Bearer dw_test_…" "http://127.0.0.1:8000/api/v1/jobs?kind=file_split&limit=10"
```

**Postman (hecho).** GET `http://127.0.0.1:8000/api/v1/jobs` (sin UUID). Bearer, Body none. HTTP **200**. Query `kind`/`limit` en Params es opcional (sin `kind` el listado mezcla kinds de la compañía).

| KEY | TYPE | VALUE |
|-----|------|--------|
| Method | — | `GET` |
| URL | — | `{{base}}/api/v1/jobs` |
| Authorization | Bearer Token | `{{key}}` |
| Headers | — | ninguno extra |
| Body | none | — |

**Params** (mismo esquema; TYPE = Text):

| KEY | TYPE | VALUE |
|-----|------|--------|
| `kind` | Text | `file_split` |
| `limit` | Text | `10` |

Paso 8 Postman cerrado. Siguiente: **Paso 10**.

| Pieza del comando | Valor que corresponde |
|-------------------|------------------------|
| `curl.exe` | Cliente HTTP de Windows. No use el alias `curl` de PowerShell. |
| `-sS` | Silencioso pero muestra errores de red. |
| (no hay `-X`) | GET. No es un run: no usa `-F` ni `Idempotency-Key`. |
| `-H "Authorization: Bearer dw_test_…"` | Mismo Bearer. Scope: `jobs:read`. |
| Comillas en la URL | En PowerShell, `&` parte el comando. |
| Path `/api/v1/jobs` | Listado de la **compañía** del token. Sin UUID. |
| Query `kind=file_split` | Solo Splits. Sin `kind`: une Gate, Clean, pipeline, etc. `file_split` y `file_merge` son la misma tabla, distinta `summary.operation`. |
| Query `limit=10` | Tamaño de página (default 20 si omite `limit`). |
| (no está en el ejemplo) `offset` | Desde qué ítem (0, 10, 20…). |
| (no está en el ejemplo) `status` | Filtrar por estado de máquina. |

**Lo que salió en esta prueba** (terminal, no un archivo):

| Campo | Valor |
|-------|--------|
| `ok` | `true` |
| `user_message` | «Listado de jobs.» |
| `jobs` | Array de envelopes (mismo shape que el GET detalle). |
| `total` | `6` |
| `limit` | `10` |
| `offset` | `0` |

Hay **6** Splits en la compañía y pidió hasta 10: caben en una página. El **primero** es el del Paso 7:

| Campo (primer ítem) | Valor |
|---------------------|--------|
| `job_id` | `481ee7ff-e129-4525-82a3-d3608237d6ca` |
| `kind` / `project_slug` | `file_split` / `prueba-02-txtd` |
| `status` | `completed` |
| `summary.files_out` / `rows_read` | `6` / `49` (el manifiesto del Paso 8 B tenía `parts_count: 4`; el listado replica el summary del job) |
| `artifacts.report_url` | `/api/v1/jobs/481ee7ff-…/report?token=…` (TTL 86400). **No** copie el token a un chat. |
| `artifacts.output_url` | Ausente (igual que en el detalle). |
| `audit.trigger_source` | `api` |
| `audit.api_client_id` | UUID del cliente de máquina |
| `audit.idempotency_key` | `prueba-post-001` |

Los **otros cinco** son corridas **UI** (`trigger_source: ui`, `api_client_id` y `idempotency_key` nulos): slugs `pq-fp-fsm-01`, `qa-pruebas-diseno-funcion-01`, `prueba-03-xls`, otra de `prueba-02-txtd`, `prueba01` (`version: v4`). Ninguno trae `output_url`. El listado **no** se limita a jobs disparados por esta key: es la compañía.

No pegue la respuesta completa (tokens de artifact) en tickets. Basta `job_id` + `kind`.

### Qué no hacer

- No vuelva a POST run para “consultar”.  
- No invente otro UUID.  
- No asuma que todo kind tiene `output`.  
- Scout: detalle 200; report/output 404.

### Si algo falla

| Qué ocurre | Qué significa |
|------------|----------------|
| `GET : The term 'GET' is not recognized` | Pegó el método HTTP en PowerShell. Use `curl.exe` (comando A). Ver Paso 10. |
| `Enter host password for user …` | Copió las llaves `{ }` alrededor del UUID. PowerShell trata `{…}` como script. Ctrl+C y repita **sin** llaves. |
| 403 · `insufficient_scope` y el `.bin` es JSON de error | El `-o` guardó el cuerpo del 403, no el manifiesto. Falta scope `artifacts:download` (cliente viejo). Con el scope, `informe2.bin` es el manifiesto. Detalle en el [Paso 10](#paso-10--errores-frecuentes-rotarrevocar-cancelar-en-construcción). |
| 404 en detalle | Id de otra compañía, typo, o aún no existe. |
| 404 JSON «El artifact no está disponible.» en `salida.bin` | El job **existe**; no hay un solo archivo de salida (Split de 6 partes). Un pipeline configurado no cambia este UUID. Ver Paso 10. |
| Archivo `utputFormat` (HTML 404 de Django en `/api/v1/jobs/`) | PowerShell se comió `/output` de la URL. Ver [Paso 10](#paso-10--errores-frecuentes-rotarrevocar-cancelar-en-construcción). |
| 404 artifact expirado | Pasó el TTL (horas del Paso 4). |
| 200 en detalle y el historial UF no lo muestra | Mismo id; recargue historial de **esa** app (Split ≠ Gate). |
| HTML 404 · path `/j/api/v1/jobs/…/report` | Typo: sobra `/j/` en la URL. Use `/api/v1/jobs/…/report`. |

### Listo para el Paso 9 cuando

**Curl** de A–D ya cumplido. **Postman 8 A–D hechos.** El Paso 9 es solo pantallas (ya hecho). Siguiente circuito HTTP: **Paso 10**.

---

## Paso 9 — Ver auditoría y qué queda en el historial de la app

> **Probado en pantalla.** US: listado `/app/platform-api/auditoria/` (eventos de **cliente**, no el UUID del job) y ficha (Auditoría + último uso). UF: detalle `/app/file-split-merge/proyectos/prueba-02-txtd/historial/481ee7ff-e129-4525-82a3-d3608237d6ca/` (corrida + partes/ZIP). Coincide con [`pa_client_audit.md`](pa_client_audit.md) vs [`pa_audit.md`](pa_audit.md) vs historial de la app.

### Qué es esto

El job **ya está** en la base. Este paso no llama a `jobs/run`. Solo **mira** tres pistas distintas que la gente mezcla bajo la palabra «auditoría»:

| Pista | Dónde | Qué registra | Qué **no** es |
|-------|--------|----------------|---------------|
| **1. Auditoría API** (menú US) | `/app/platform-api/auditoria/` | Ciclo de vida del **cliente/key**: alta, scopes, rotar, revelar, revocar | No lista cada `POST /jobs/run`. No tiene el `job_id` |
| **2. Bloque `audit` del JSON** | Paso 8 A / D | Disparo de **ese** job: `trigger_source=api`, cliente, idempotencia, IP, tiempos | No es una pantalla US aparte; viaja en el envelope HTTP |
| **3. Historial de la app** | File Split/Merge (esta prueba) | La **corrida** con el mismo UUID: partes, ZIP, TTL, «ejecutado por» | No es el menú **Auditoría API**. Gate/Clean/Pipe tienen el suyo |

Un `GET /whoami` **no** crea fila en (1). El pulso de uso del cliente es `último uso` en la ficha (`last_used_at`). El tablero de File Pipeline **no** cuenta este Split suelto (`pipeline_id: null`).

### Qué necesita antes

- Paso 8 hecho: `job_id` `481ee7ff-e129-4525-82a3-d3608237d6ca`, slug `prueba-02-txtd`, `kind=file_split`.  
- Sesión **US** para la pista 1 (mismo menú del Paso 1).  
- Para la pista 3: un usuario que vea **Archivos de trabajo** → **File Split/Merge** (típicamente **UF** con membresía en ese proyecto). Si el US no muestra esa familia, cierre sesión y entre con UF.  
- El código del cliente de máquina (ficha API), no hace falta pegar la key.

### Qué hacer

#### A. Auditoría del cliente (US) — pista 1

1. Entre como US. Barra izquierda: **Auditoría API**.  
2. URL:  
   `http://127.0.0.1:8000/app/platform-api/auditoria/`  
   Título: **Auditoría de clientes de máquina**.  
3. Debe ver una tabla (Fecha, Cliente, Acción, Actor, Resumen). Filtro **Acción**. Eventos típicos de esta prueba: **Alta** (`created`) al crear el cliente del Paso 2; **Cambio** (`updated`) si marcó `artifacts:download` después. **No** busque aquí el UUID del job.  
4. Pulse el **código** del cliente (columna Cliente) o, desde la ficha, el botón **Auditoría**:  
   `http://127.0.0.1:8000/app/platform-api/clientes/{id-del-cliente}/auditoria/`  
   Línea de tiempo **solo** de esa key.  
5. **Ver** abre el evento (antes/después de scopes; nunca el secreto).  
6. Vuelva a **API** → ficha del cliente. Si ya corrió `jobs/run` o `whoami`, debe aparecer **último uso** (fecha/hora). Eso confirma que la máquina autenticó; no sustituye el historial Split.

#### B. El `audit` que ya tiene en el JSON — pista 2

No hace falta otro curl si guardó el detalle del Paso 8 A. Compruebe:

| Campo | En esta prueba |
|-------|----------------|
| `audit.trigger_source` | `api` |
| `audit.api_client_id` / `triggered_by_api_client_id` | UUID del cliente (el listado D lo trajo) |
| `audit.idempotency_key` | `prueba-post-001` |
| `audit.correlation_id` | hex de traza |
| `audit.client_ip` | `127.0.0.1` |
| `audit.user_agent` | `curl/…` |
| `audit.job_id` | el mismo UUID |

Los ítems D con `trigger_source: ui` son corridas de pantalla: **no** saldrán como alta/rotación en Auditoría API; sí en el historial de su proyecto.

#### C. Historial File Split/Merge — pista 3 (aquí están las partes)

1. Entre con el usuario que ve File Split/Merge.  
2. **Archivos de trabajo** → **File Split/Merge** → proyecto **`prueba-02-txtd`** → **Historial**.  
   URL:  
   `http://127.0.0.1:8000/app/file-split-merge/proyectos/prueba-02-txtd/historial/`  
3. Busque el job. El id corto del listado es el prefijo del UUID; el detalle usa el UUID completo:  
   `http://127.0.0.1:8000/app/file-split-merge/proyectos/prueba-02-txtd/historial/481ee7ff-e129-4525-82a3-d3608237d6ca/`  
4. En el detalle: estado, operación Split, versión publicada, filas, partes, TTL. Tabla **Salidas / manifiesto**: un enlace **Descargar** por parte (los `.txt` que `/output` no empaqueta). Si el rol y el TTL lo permiten: **Descargar ZIP**.  
5. **Ejecutado por**: no es el nombre de la key. El motor guarda el usuario **actor** (`created_by` del cliente API o el dueño del proyecto). Puede verse un usuario US/UF, no `dw_test_…`.

Otro `kind` → otro historial (`/app/file-gate/…`, Clean, etc.). No busque este UUID en Gate ni en el tablero Pipe.

### Qué debe ver

- US, Auditoría API: filas de **cliente**, no de jobs.  
- Ficha del cliente: **último uso** reciente.  
- UF, historial `prueba-02-txtd`: la corrida `481ee7ff-…` **completed**, mismas filas que el manifiesto; descargas de partes o ZIP.  
- El JSON `audit.trigger_source=api` encaja con esa fila (mismo id).

### Qué no hacer todavía

- No rote ni revoque la key (Paso 10).  
- No borre la corrida del historial «para probar»: pierde artifacts.  
- No busque el `job_id` en Auditoría API.  
- No abra el historial de **otro** slug (`pq-fp-fsm-01`, etc.): son otros jobs del listado D.

### Si algo falla

| Qué ocurre | Qué significa |
|------------|----------------|
| No aparece **Auditoría API** | No está en perfil US. |
| Auditoría vacía | No se ha creado/editado ningún cliente en esta compañía. El run HTTP no llena esta tabla. |
| Historial Split 404 / vacío | Slug incorrecto, sin membresía, u otra compañía. |
| No ve File Split/Merge en el menú | Está en sesión US (familia API). Use UF o pegue la URL del historial si su usuario tiene acceso. |
| Job en historial pero sin Descargar / ZIP | Rol consultor (solo metadatos) o **TTL expirado** (política del Paso 4 / días del historial). |
| «Ejecutado por» es una persona, no la API | Esperado: actor humano del cliente; el sello máquina está en `audit` del JSON. |
| No está en el tablero Pipe | Job suelto (`pipeline_id: null`). El tablero cuenta cadenas. |

### Listo para el Paso 10 cuando

**Cumplido.** Las dos URLs de revisión coinciden con el producto. Siguiente: completar en el Paso 10 **rotar key**, **revocar cliente** y **cancelar job** (aún no ejecutados). Los fallos de curl del Paso 8 ya están ahí.

---

## Paso 10 — Errores frecuentes, rotar, revocar, cancelar

### Qué es esto

Tres acciones distintas. Ninguna rehace jobs **pasados**. El Split `481ee7ff-…` sigue en el historial aunque rote o revoque.

| Acción | Dónde | Para qué | ¿Nueva key? |
|--------|--------|----------|-------------|
| **A. Rotar** | Ficha US → **Rotar key** | Compromiso, caducidad o política. Misma identidad (código, scopes, entorno) | **Sí.** La anterior deja de autenticar. Reveal de un solo uso (como el Paso 2) |
| **B. Cancelar** | `POST /api/v1/jobs/{id}/cancel` | Abortar un job **aún no terminal** (cola `wait=async` o pipeline no cerrado) | No |
| **C. Revocar** | Ficha US → **Revocar** | Baja del integrador. El **cliente** queda inhabilitado | No: *ninguna* key de ese cliente sirve. No se “des-revoca” |

Rotar ≠ crear otro cliente. Revocar ≠ rotar. Cambiar scopes (Paso 8) **no** rota.

**Orden de esta prueba:** A (rotar + `whoami` con key vieja/nueva) → B (cancelar el Split: espere **409**) → C (revocar **al final**: pierde el sandbox). No revoque antes de copiar la key rotada.

Los fallos de curl del Paso 8 están más abajo ([Fallos ya vistos](#fallos-ya-vistos-paso-8)).

### Qué necesita antes

- Sesión **US** y ficha del cliente sandbox de esta prueba (activo).  
- La key **actual** en el cofre (la usará una vez más para demostrar el 401).  
- Scope `jobs:cancel` **antes** del POST cancel (márquelo y **Guardar configuración**; no hace falta rotar por eso).  
- El `job_id` del Split (ya `completed`).

### Qué hacer

#### A. Rotar key — **hágalo ahora**

> **Probado (pantalla + 401 key vieja).** Cliente `api-qa-p01`. Rotar → Key emitida · mensaje «Key rotada…» · Auditoría **Rotación** (`key_rotated`). El `job_id` Split no cambia. **No** pegue keys en el chat ni en este archivo.

1. US → **API** → ficha del cliente sandbox.  
2. Pulse **Rotar key** (POST). No es el botón Guardar configuración.  
3. Llega a **Key emitida** (`…/clientes/{id}/key/`), igual que el Paso 2. Copie el Bearer (`dw_test_…`) al cofre. La pantalla no se puede repetir.  
4. Mensaje de producto: «Key rotada. Copie la nueva key ahora; la anterior deja de autenticar.»  
5. En Auditoría API (Paso 9 A) debe aparecer acción **Rotación** (`key_rotated`). El `job_id` Split **no** cambia.  
6. Terminal (key **vieja**; debe fallar). El circuito pide `whoami`; en esta prueba también fallaron `GET …/output` y `GET …/jobs?kind=file_split` con el mismo JSON:

```text
curl.exe -sS -H "Authorization: Bearer dw_test_VIEJA" "http://127.0.0.1:8000/api/v1/whoami"
```

**Hecho (curl, key vieja):** `ok: false`, `error_code: invalid_token`, «Credencial ausente o inválida.» (también en `/output` y listado).

**Postman (pendiente).** Dos requests `GET` `{{base}}/api/v1/whoami`: (1) Environment `key` = key **vieja** → 401; (2) `key` = key **nueva** (sin pegarla en el chat) → 200.

7. **Hecho (curl, key nueva).** `GET /api/v1/whoami` HTTP **200**. `ok: true`, `client_code`: `api-qa-p01`, `environment`: `sandbox`, `company`: `ACME`. Scopes: `jobs:run`, `jobs:read`, `jobs:cancel`, `pipeline:run`, `artifacts:download`. `process_policy` igual que el Paso 6 A (`max_upload_bytes` 52428800, `rate_per_minute` 60, `artifact_ttl_hours` 24, `require_published`: true). Actualice `{{key}}` en Postman. Opcional: GET detalle `481ee7ff-…` con la nueva → 200 (mismo job).

**Qué no hacer:** no recargue **Key emitida** sin haber copiado; no revoque todavía; no cree un cliente nuevo “por si acaso” (eso es otra identidad).

#### B. Cancelar job

> **Probado en curl — 409 correcto.** El Split `481ee7ff-…` está `completed`; Split/Merge no pasan por la cola DMS.

1. En la ficha, marque `jobs:cancel` si falta → Guardar.  
2. Use la key **vigente** (la nueva si ya rotó):

```text
curl.exe -sS -X POST -H "Authorization: Bearer dw_test_…" "http://127.0.0.1:8000/api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca/cancel"
```

| Pieza | Valor |
|-------|--------|
| `-X POST` | Aquí sí: cancelar no es GET. |
| URL `…/cancel` | Mismo UUID, entre comillas. |
| Scope | `jobs:cancel`. Si falta: 403 `insufficient_scope`. |

**Postman (pendiente).** Method `POST`. URL `{{base}}/api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca/cancel`. Auth Bearer (key **vigente**). Body none. Mismo 409 que curl.

**Hecho (curl).** `ok: false`, `error_code: cancel_not_allowed`, `user_message`: «Este job ya no se puede cancelar.», `errors[]` con `field`: `status`. El historial Split **no** se borra.

Cancelar **200** (`status: cancelled`) solo aplica a:

- Job **DMS** (Gate/FilePipe) en cola (`wait=async`, aún no terminal).  
- Pipeline run que no esté completed/failed/cancelled.

Match, Scout, Clean, Split, Merge: 409 aunque “sigan corriendo” en otro sentido: el módulo de cancel no los aborta. Un 200 de cancel **no** se obtiene con este UUID.

#### C. Revocar cliente — **después** de A (y B si quiere)

> **Probado.** Revocar cerró el sandbox de `api-qa-p01`. Las keys dejan de autenticar. Los jobs ya corridos no se borran.

1. Ficha del cliente **activo** → **Revocar**. Confirme el diálogo (las keys dejan de autenticar).  
2. Mensaje: «Cliente revocado. Ya no puede autenticar llamadas.» Estado **revocado**; desaparecen Rotar y Guardar.  
3. Auditoría: acción **Revocación** (`revoked`).  
**Hecho (UI + whoami).** Cliente **revocado**. `whoami` con la última key: **401**. No hay “des-revocar”: hace falta **otro** cliente (Paso 2) para seguir integrando.

**Postman (pendiente, opcional).** `GET` `{{base}}/api/v1/whoami` con la última `key` → 401 (el cliente ya está revocado).

Los jobs ya corridos permanecen en historial y en `GET /jobs/{id}` **si** usa **otro** cliente activo de la **misma** compañía (scope `jobs:read`). Con el cliente revocado no hay Bearer válido.

### Si algo falla (A–C)

| Qué ocurre | Qué significa |
|------------|----------------|
| Rotó y no copió | No hay “ver de nuevo”. Vuelva a **Rotar**. La key intermedia también queda inválida. |
| 401 con la key que cree nueva | Espacio, recorte, o pegó la vieja. `whoami` primero. |
| Revocar en gris / no está | Ya está revocado. |
| Cancel 403 | Falta `jobs:cancel`. |
| Cancel 409 en el Split | Esperado. |
| Cancel 404 | UUID ajeno o typo. |

### Listo cuando

**Curl/UI de A–C cumplido** (`api-qa-p01` revocado). Postman 10 A–C opcionales. Siguiente circuito de producto: manual de **pipelines**.

---

### Fallos ya vistos (Paso 8)

#### PowerShell: `GET : The term 'GET' is not recognized`

**Síntoma:** en la terminal escribió:

```text
GET /api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca
```

Respuesta: `GET : The term 'GET' is not recognized as the name of a cmdlet…` (`CommandNotFoundException`). **No** hubo llamada HTTP.

**Por qué:** en el manual, `GET /api/v1/jobs/{id}` nombra el **path HTTP**. PowerShell busca un programa llamado `GET`. El cliente es **`curl.exe`**.

**Qué hacer:** el comando A del Paso 8 (mismo Bearer que ya usó; sustituya `dw_test_…`):

```text
curl.exe -sS -H "Authorization: Bearer dw_test_…" "http://127.0.0.1:8000/api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca"
```

Debe imprimir JSON en la terminal (`user_message`: «Job encontrado.»). Busque si existe `artifacts.output_url`. En este Split no estará.

#### Informe (`informe.bin`) es un JSON de error, no el manifiesto

**Síntoma (prueba anterior, cliente sin `artifacts:download`):** el comando B no muestra error en la terminal; al abrir el archivo:

```json
{"ok": false, "error_code": "insufficient_scope", "user_message": "No tiene permiso para esta operación.", "errors": []}
```

**Por qué:** `-o` guarda **cualquier** cuerpo HTTP. `-sS` no trata un **403** como fallo de curl. El GET `…/report` con **solo Bearer** exige **`artifacts:download`**.

**Qué hacer:** marque el scope en la ficha US (no hace falta rotar la key) **o** cree el cliente de nuevo con ese scope (como en el circuito desde el Paso 2). Vuelva a bajar a **otro** archivo (`informe2.bin`) para no confundirlo con el 403 viejo.

**Ya validado:** con scope, el mismo path y el mismo `job_id` generan el manifiesto (`operation: split`, `parts_count`, `parts[]`). Ver Paso 8 B. Para el HTTP: `-w "\nHTTP %{http_code}\n"`.

#### `utputFormat` es HTML 404; la URL `…/output` se partió en PowerShell

**Síntoma:** ejecutó el comando C del Paso 8:

```text
curl.exe -sS -L -H "Authorization: Bearer dw_test_…" -o salida.bin http://127.0.0.1:8000/api/v1/jobs/{job_id}/output
```

Aparece un archivo **`utputFormat`** (nombre raro, no `salida.bin`). Al abrirlo: cabeceras HTTP + HTML *Page not found at `/api/v1/jobs/`* (404 de Django en debug). Se puede ver en el navegador, pero **no** es el artifact.

**Por qué (dos capas):**

1. **PowerShell** trata el sufijo `/output` de la URL **sin comillas** como un parámetro (`-Output` / `-OutputFormat`). La petición llega a `/api/v1/jobs/` **sin** UUID. `-o` también choca con `-OutputFormat` (de ahí el nombre `utputFormat`).  
2. **Aunque la URL llegue bien:** en un Split con **varios** archivos no hay `output_url`. El GET `…/output` correcto responde **404 JSON** (`El artifact no está disponible` / `No se encontró el recurso`). Eso no anula el Split; las partes están en el historial de File Split/Merge.

**Qué hacer:**

```text
curl.exe -sS -L -H "Authorization: Bearer dw_test_…" --output salida.bin "http://127.0.0.1:8000/api/v1/jobs/481ee7ff-e129-4525-82a3-d3608237d6ca/output"
```

- Use **`--output`** (no `-o`) y **comillas** en toda la URL.  
- Añada `-w "\nHTTP %{http_code}\n"`. En este Split espere **404** y JSON, no un ZIP con las 6 partes.  
- Lo mismo aplica a `…/report` si PowerShell recorta el path: `--output informe.bin` y URL entre comillas.  
- Puede borrar `utputFormat`.

#### `salida.bin` es JSON `not_found` — «El artifact no está disponible.»

**Síntoma:** el comando C (ya con `--output` y URL entre comillas) no pide password ni genera `utputFormat`. En `salida.bin`:

```json
{"ok": false, "error_code": "not_found", "user_message": "El artifact no está disponible.", "errors": []}
```

HTTP **404**. El Bearer y el `job_id` **sí** coinciden (si el UUID no existiera, el mensaje sería «No se encontró el recurso.»).

**Por qué:** `GET …/output` solo entrega bytes cuando hay **un** archivo de salida (`output_stored_path` o `outputs` con exactamente 1 ítem). El job de esta prueba es un **Split** con `files_out: 6`. El envelope del GET detalle **no** trae `artifacts.output_url`. El código no empaqueta las 6 partes en un ZIP.

Un pipeline publicado (código p. ej. `exodo-tdc-amd-01`) con Gate, Clean, Split, etc. **no** adjunta esos archivos a este UUID. Este `job_id` es el del **Split suelto** (`kind=file_split`, proyecto `prueba-02-txtd`), no el `job_id` / `pipeline_run_id` de una corrida de esa cadena.

**Qué hacer:**

1. Primero el **comando A** (`curl.exe` al detalle, sin `/output`). Si **no** hay `artifacts.output_url`, no vuelva a pedir `/output` esperando 200. No escriba `GET` en PowerShell.  
2. Para este Split: baje el **report** (`…/report`) — es el manifiesto con la lista de partes. Los `.txt` (o el formato de cada parte) están en el **historial UF de File Split/Merge**, no en este path.  
3. Si quiere un fichero único por API: ejecute un kind que deje un solo output (Clean, DMS, Merge a un archivo, o un **run de pipeline** y use el `job_id` de **esa** corrida, no el del Split del Paso 7).  
4. El 404 no anula el Split: el job ya está `completed`.

---

*Circuito curl 1–10 **hecho**. Postman 6–8 **hecho**; Postman 10 opcional. Pipelines: [`MANUAL_USUARIO_API_PIPELINE.md`](MANUAL_USUARIO_API_PIPELINE.md).*


