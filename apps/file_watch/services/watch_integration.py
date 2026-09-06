"""M10: mapa de integración (Scheduler watch_id, claim, Railway worker)."""

from __future__ import annotations

LAYERS = [
    {
        "name": "De dónde",
        "question": "¿SFTP / carpeta / API push?",
        "owner": "File Watch · Origen (M2)",
    },
    {
        "name": "Qué archivo",
        "question": "¿Lote + hash en storage del tenant?",
        "owner": "File Watch · Intake (M3)",
    },
    {
        "name": "Hacia qué runner",
        "question": "Job / pipeline / diferir",
        "owner": "File Watch · Enrutado (M4)",
    },
    {
        "name": "¿Cuándo encolar?",
        "question": "Al llegar vs solo pending",
        "owner": "File Watch · Disparo (M5)",
    },
    {
        "name": "Cuándo (reloj)",
        "question": "Cron del plan con watch_id",
        "owner": "File Scheduler",
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
        "role": "POST de máquina; CRUD de bandejas fuera de API en MVP",
        "same_runner": True,
    },
    {
        "code": "watch",
        "label": "File Watch",
        "role": "Llegó el archivo; fire al llegar o lote pending",
        "same_runner": True,
    },
    {
        "code": "scheduler",
        "label": "File Scheduler",
        "role": "Claim del lote por código de bandeja (watch_id)",
        "same_runner": True,
    },
]

RAILWAY = [
    {
        "piece": "Web Django",
        "role": "CRUD de bandeja M1–M9, lotes, auditoría, avisos, este mapa",
        "proc": "web",
    },
    {
        "piece": "Worker Watch",
        "role": "Poll carpeta gestionada; intake; fire M5 o dejar pending",
        "proc": "watch",
    },
    {
        "piece": "Worker Scheduler",
        "role": "Claim pending por watch_id (bridge) → mismo runner",
        "proc": "scheduler",
    },
]

BRIDGE = [
    "Plan Destino: input_origin=watch + código de bandeja = slug Watch.",
    "Tick: claim_pending_batch → content_hash / storage_key → runner.",
    "Sin pending → schedule_missing_input (código Scheduler, no watch_*).",
    "Artifact (hash fijo en el plan) ≠ Watch (código de bandeja).",
]

WORK_MODE = [
    "UI de bandejas + worker de intake (MVP).",
    "Endpoint api_push por bandeja (token o sesión autenticada).",
    "File Gate no configura IFS: las rutas viven en Watch.",
]


def map_context() -> dict:
    return {
        "layers": LAYERS,
        "channels": CHANNELS,
        "railway": RAILWAY,
        "bridge": BRIDGE,
        "work_mode": WORK_MODE,
        "worker_command": "process_watch_intake --loop --interval 60",
        "claim_hint": "claim_pending_batch(company, watch_slug, schedule_slug=…)",
    }
