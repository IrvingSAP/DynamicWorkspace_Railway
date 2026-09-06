"""M8: catálogo error_code ↔ user_message (capas 2 y 3). El código no se muestra al usuario."""

from __future__ import annotations

VALIDATION_REQUIRED = "validation_required"
SLUG_TAKEN = "schedule_slug_taken"
FORBIDDEN = "schedule_forbidden"
CRON_INVALID = "schedule_cron_invalid"
TIMEZONE_INVALID = "schedule_timezone_invalid"
NO_PUBLISHED = "schedule_no_published_target"
MISSING_INPUT = "schedule_missing_input"
TARGET_CROSS_TENANT = "schedule_target_cross_tenant"
DEPENDENCY_CYCLE = "schedule_dependency_cycle"
DEPENDENCY_CROSS_TENANT = "schedule_dependency_cross_tenant"
INCOMPLETE = "schedule_incomplete"
PAUSED = "schedule_paused"
OVERLAP_SKIP = "schedule_overlap_skip"
MISFIRE = "schedule_misfire"
ENQUEUE_FAILED = "schedule_enqueue_failed"
ARTIFACT_NOT_FOUND = "schedule_artifact_not_found"
RUNNER_UNSUPPORTED = "schedule_runner_unsupported"
NOTIFY_WEBHOOK_INVALID = "schedule_notify_webhook_invalid"
NOTIFY_EMAIL_INVALID = "schedule_notify_email_invalid"

OPAQUE_CODES = frozenset({TARGET_CROSS_TENANT, DEPENDENCY_CROSS_TENANT})

MESSAGES = {
    VALIDATION_REQUIRED: "Complete los campos obligatorios.",
    SLUG_TAKEN: "Ese código ya existe en la compañía.",
    FORBIDDEN: "No tiene permiso para cambiar este plan.",
    CRON_INVALID: "La programación no es válida. Consulte la Ayuda.",
    TIMEZONE_INVALID: "La zona horaria no es válida.",
    NO_PUBLISHED: "El destino no tiene una versión publicada operativa.",
    MISSING_INPUT: (
        "Falta el archivo de entrada. No se puede disparar sin Watch o una referencia."
    ),
    DEPENDENCY_CYCLE: "El padre no puede ser el mismo destino del plan.",
    INCOMPLETE: (
        "Complete el destino y el disparador (horario o dependencia) para activar."
    ),
    PAUSED: "El plan no está activo.",
    OVERLAP_SKIP: (
        "Se omitió este horario porque el run anterior sigue en curso."
    ),
    MISFIRE: (
        "No se ejecutó a tiempo (el programador no estaba disponible). "
        "Se sigue con la próxima ventana."
    ),
    ENQUEUE_FAILED: (
        "No se pudo encolar el Job. Inténtelo más tarde o revise la cola."
    ),
    ARTIFACT_NOT_FOUND: (
        "No se encontró el archivo del artifact en storage. Verifique el hash."
    ),
    RUNNER_UNSUPPORTED: (
        "Este tipo de destino aún no se ejecuta desde el Scheduler."
    ),
    NOTIFY_WEBHOOK_INVALID: "El webhook debe empezar por https://.",
    NOTIFY_EMAIL_INVALID: "Un miembro marcado no tiene correo en su cuenta.",
}

CATALOG = [
    {
        "code": VALIDATION_REQUIRED,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline",
        "user_message": MESSAGES[VALIDATION_REQUIRED],
    },
    {
        "code": SLUG_TAKEN,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline",
        "user_message": MESSAGES[SLUG_TAKEN],
    },
    {
        "code": FORBIDDEN,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Modal",
        "user_message": MESSAGES[FORBIDDEN],
    },
    {
        "code": CRON_INVALID,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline + alerta",
        "user_message": MESSAGES[CRON_INVALID],
    },
    {
        "code": TIMEZONE_INVALID,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline",
        "user_message": MESSAGES[TIMEZONE_INVALID],
    },
    {
        "code": NO_PUBLISHED,
        "layer": "2",
        "layer_label": "2 y 3",
        "channel": "Inline / Actividad",
        "user_message": MESSAGES[NO_PUBLISHED],
    },
    {
        "code": MISSING_INPUT,
        "layer": "2",
        "layer_label": "2 y 3",
        "channel": "Inline / Actividad",
        "user_message": MESSAGES[MISSING_INPUT],
    },
    {
        "code": DEPENDENCY_CYCLE,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline + alerta",
        "user_message": MESSAGES[DEPENDENCY_CYCLE],
    },
    {
        "code": INCOMPLETE,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Modal",
        "user_message": MESSAGES[INCOMPLETE],
    },
    {
        "code": PAUSED,
        "layer": "3",
        "layer_label": "3 · Tick",
        "channel": "Actividad",
        "user_message": MESSAGES[PAUSED],
    },
    {
        "code": OVERLAP_SKIP,
        "layer": "3",
        "layer_label": "3 · Tick",
        "channel": "Actividad (omitido)",
        "user_message": MESSAGES[OVERLAP_SKIP],
    },
    {
        "code": MISFIRE,
        "layer": "3",
        "layer_label": "3 · Tick",
        "channel": "Actividad",
        "user_message": MESSAGES[MISFIRE],
    },
    {
        "code": ENQUEUE_FAILED,
        "layer": "3",
        "layer_label": "3 · Tick",
        "channel": "Actividad",
        "user_message": MESSAGES[ENQUEUE_FAILED],
    },
    {
        "code": ARTIFACT_NOT_FOUND,
        "layer": "3",
        "layer_label": "3 · Tick",
        "channel": "Actividad",
        "user_message": MESSAGES[ARTIFACT_NOT_FOUND],
    },
    {
        "code": RUNNER_UNSUPPORTED,
        "layer": "3",
        "layer_label": "3 · Tick",
        "channel": "Actividad",
        "user_message": MESSAGES[RUNNER_UNSUPPORTED],
    },
    {
        "code": NOTIFY_WEBHOOK_INVALID,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline",
        "user_message": MESSAGES[NOTIFY_WEBHOOK_INVALID],
    },
    {
        "code": NOTIFY_EMAIL_INVALID,
        "layer": "2",
        "layer_label": "2 · CRUD",
        "channel": "Inline",
        "user_message": MESSAGES[NOTIFY_EMAIL_INVALID],
    },
]

MSG_REQUIRED = MESSAGES[VALIDATION_REQUIRED]
MSG_SLUG_TAKEN = MESSAGES[SLUG_TAKEN]
MSG_FORBIDDEN = MESSAGES[FORBIDDEN]
MSG_CRON_INVALID = MESSAGES[CRON_INVALID]
MSG_TIMEZONE_INVALID = MESSAGES[TIMEZONE_INVALID]
MSG_NO_PUBLISHED = MESSAGES[NO_PUBLISHED]
MSG_MISSING_INPUT = MESSAGES[MISSING_INPUT]
MSG_CYCLE = MESSAGES[DEPENDENCY_CYCLE]
MSG_INCOMPLETE = MESSAGES[INCOMPLETE]
MSG_PAUSED = MESSAGES[PAUSED]
MSG_OVERLAP = MESSAGES[OVERLAP_SKIP]
MSG_MISFIRE = MESSAGES[MISFIRE]
MSG_ENQUEUE_FAILED = MESSAGES[ENQUEUE_FAILED]
MSG_ARTIFACT_NOT_FOUND = MESSAGES[ARTIFACT_NOT_FOUND]
MSG_RUNNER_UNSUPPORTED = MESSAGES[RUNNER_UNSUPPORTED]
MSG_NOTIFY_WEBHOOK = MESSAGES[NOTIFY_WEBHOOK_INVALID]
MSG_NOTIFY_EMAIL = MESSAGES[NOTIFY_EMAIL_INVALID]
MSG_TRIGGER_SAVED = "Disparador guardado."
MSG_NOTIFY_SAVED = "Avisos guardados."
MSG_CREATED = "Plan creado correctamente."
MSG_CRON_SAVED = "Programación guardada."
MSG_TARGET_SAVED = "Destino guardado."
MSG_OVERLAP_SAVED = "Política de solape guardada."
MSG_PAUSED_OK = "Plan pausado."
MSG_RESUMED = "Plan reanudado."
MSG_ARCHIVED = "Plan archivado."


def message_for(error_code: str) -> str:
    return MESSAGES.get(error_code or "", "")


def catalog_rows() -> list[dict]:
    return list(CATALOG)
