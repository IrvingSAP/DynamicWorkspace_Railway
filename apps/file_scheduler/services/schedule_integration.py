"""M10: mapa de integración (Watch, Pipeline, API, tablero, worker). No es CRUD de un plan."""

from __future__ import annotations

LAYERS = [
    {
        "name": "Cuándo",
        "question": "¿Es la hora o terminó el Job A?",
        "owner": "File Scheduler (cron · dependencia)",
    },
    {
        "name": "Dónde está el fichero",
        "question": "Watch, artifact o sin archivo",
        "owner": "File Watch · destino del plan (M3)",
    },
    {
        "name": "Cómo se transforma",
        "question": "App de archivo o pipeline publicado",
        "owner": "Gate, Pipe, Clean… · File Pipeline",
    },
]

CHANNELS = [
    {
        "code": "ui",
        "label": "UI Ejecutar",
        "role": "Humano lanza un Job o un pipeline_run",
        "same_runner": True,
    },
    {
        "code": "api",
        "label": "PLATFORM API",
        "role": "POST de máquina; CRUD de planes fuera de API en MVP",
        "same_runner": True,
    },
    {
        "code": "watch",
        "label": "File Watch",
        "role": "Llegó el archivo; el plan puede reusar ese lote a las 02:00",
        "same_runner": True,
    },
    {
        "code": "scheduler",
        "label": "File Scheduler",
        "role": "Hora (cron) · trigger_source=scheduler + schedule_id",
        "same_runner": True,
    },
    {
        "code": "dependency",
        "label": "Dependencia",
        "role": "Tras Job/pipeline A · trigger_source=dependency",
        "same_runner": True,
    },
]

RAILWAY = [
    {
        "piece": "Web Django",
        "role": "CRUD del plan, Actividad, Auditoría, avisos, este mapa",
        "proc": "web",
    },
    {
        "piece": "Worker",
        "role": "Evalúa planes Activos en modo reloj; no evalúa trigger_mode=dependency",
        "proc": "scheduler",
    },
    {
        "piece": "Señales Django",
        "role": "Al terminar Job/pipeline: fire por dependencia y avisos de run fallido",
        "proc": "web (mismo runtime)",
    },
]

WORK_MODE = [
    "UI de planes + worker/monitor (MVP, esta implementación).",
    "CRUD de schedules por HTTP = posterior; no bloquea M1–M9.",
    "Nodo schedule en el canvas de Pipeline = posterior (mismas reglas de auditoría).",
]


def map_context() -> dict:
    return {
        "layers": LAYERS,
        "channels": CHANNELS,
        "railway": RAILWAY,
        "work_mode": WORK_MODE,
        "worker_command": "process_schedule_ticks --loop --interval 60",
    }
