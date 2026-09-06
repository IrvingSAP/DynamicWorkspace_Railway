"""M2: validación de cron/presets y próximas ventanas (sin disparar)."""

from __future__ import annotations

import calendar
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apps.file_scheduler.services import schedule_errors as err

CRON_FIELD_NAMES = ["minuto", "hora", "día del mes", "mes", "día de la semana"]
CRON_FIELD_RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
HELP_NOTE = " Consulte la Ayuda para completar la información correctamente."
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)")
DEFAULT_TIMEZONE = "America/Caracas"
COMMON_TIMEZONES = [
    "America/Caracas",
    "America/Bogota",
    "America/Mexico_City",
    "America/Lima",
    "America/Santiago",
    "America/Buenos_Aires",
    "America/New_York",
    "Europe/Madrid",
    "UTC",
]
KIND_DAILY = "daily"
KIND_WEEKDAYS = "weekdays"
KIND_WEEKLY = "weekly"
KIND_MONTHLY = "monthly"
KIND_CRON = "cron"
VALID_KINDS = {KIND_DAILY, KIND_WEEKDAYS, KIND_WEEKLY, KIND_MONTHLY, KIND_CRON}
MONTHLY_LAST = "last_day"
MONTHLY_SPECIFIC = "specific"
DOW_LABELS = {0: "dom", 1: "lun", 2: "mar", 3: "mié", 4: "jue", 5: "vie", 6: "sáb"}


def _parse_int_strict(s: str) -> int | None:
    if not s.isdigit():
        return None
    return int(s)


def _valid_cron_token(token: str, min_v: int, max_v: int) -> bool:
    if not token:
        return False
    step = 1
    base = token
    if "/" in token:
        parts = token.split("/")
        if len(parts) != 2:
            return False
        base, step_s = parts
        step = _parse_int_strict(step_s)
        if step is None or step < 1:
            return False
    if base == "*":
        return True
    if "-" in base:
        rng = base.split("-")
        if len(rng) != 2:
            return False
        a = _parse_int_strict(rng[0])
        b = _parse_int_strict(rng[1])
        if a is None or b is None:
            return False
        if a < min_v or b > max_v or a > b:
            return False
        return True
    n = _parse_int_strict(base)
    if n is None or n < min_v or n > max_v:
        return False
    return True


def _valid_cron_field(field: str, min_v: int, max_v: int) -> bool:
    items = field.split(",")
    if not items:
        return False
    return all(_valid_cron_token(item, min_v, max_v) for item in items)


def validate_cron_expr(raw: str) -> tuple[bool, str]:
    expr = (raw or "").strip()
    if not expr:
        return False, (
            "Indique la expresión cron (5 campos: minuto hora día-mes mes día-semana)."
            + HELP_NOTE
        )
    parts = expr.split()
    if len(parts) != 5:
        return False, (
            "La expresión debe tener exactamente 5 campos "
            "(minuto hora día-mes mes día-semana). Ahora tiene "
            f"{len(parts)}." + HELP_NOTE
        )
    for i, part in enumerate(parts):
        min_v, max_v = CRON_FIELD_RANGES[i]
        if not _valid_cron_field(part, min_v, max_v):
            return False, (
                f"El campo «{CRON_FIELD_NAMES[i]}» no es válido (valor «{part}»). "
                f"Use * , lista (1,15), rango (1-5) o paso (*/15) dentro de "
                f"{min_v}–{max_v}." + HELP_NOTE
            )
    return True, ""


def _expand_token(token: str, min_v: int, max_v: int) -> set[int]:
    step = 1
    base = token
    if "/" in token:
        base, step_s = token.split("/", 1)
        step = int(step_s)
    if base == "*":
        return set(range(min_v, max_v + 1, step))
    if "-" in base:
        a, b = base.split("-", 1)
        start, end = int(a), int(b)
        return set(range(start, end + 1, step))
    n = int(base)
    if step > 1:
        return {v for v in range(n, max_v + 1, step)}
    return {n}


def expand_cron_field(field: str, min_v: int, max_v: int) -> set[int]:
    values: set[int] = set()
    for token in field.split(","):
        values |= _expand_token(token, min_v, max_v)
    return values


def parse_cron_sets(expr: str) -> list[set[int]] | None:
    ok, _ = validate_cron_expr(expr)
    if not ok:
        return None
    parts = expr.strip().split()
    return [
        expand_cron_field(parts[i], CRON_FIELD_RANGES[i][0], CRON_FIELD_RANGES[i][1])
        for i in range(5)
    ]


def cron_dow(dt: datetime) -> int:
    return (dt.weekday() + 1) % 7


def cron_matches(dt: datetime, sets: list[set[int]]) -> bool:
    return (
        dt.minute in sets[0]
        and dt.hour in sets[1]
        and dt.day in sets[2]
        and dt.month in sets[3]
        and cron_dow(dt) in sets[4]
    )


def resolve_timezone(name: str) -> tuple[ZoneInfo | None, str]:
    tz_name = (name or "").strip() or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(tz_name), tz_name
    except ZoneInfoNotFoundError:
        return None, tz_name


def parse_time_local(value: str) -> tuple[int, int] | None:
    m = TIME_RE.match((value or "").strip())
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2))
    if hour > 23:
        return None
    return hour, minute


def materialize_cron_expr(data: dict) -> str:
    kind = data.get("schedule_kind")
    if kind == KIND_CRON:
        return (data.get("cron_expr") or "").strip()
    parsed = parse_time_local(data.get("time_local") or "")
    if parsed is None:
        return ""
    hour, minute = parsed
    if kind == KIND_DAILY:
        return f"{minute} {hour} * * *"
    if kind == KIND_WEEKDAYS:
        return f"{minute} {hour} * * 1-5"
    if kind == KIND_WEEKLY:
        dow = data.get("day_of_week")
        return f"{minute} {hour} * * {dow}"
    if kind == KIND_MONTHLY and data.get("monthly_mode") == MONTHLY_SPECIFIC:
        dom = data.get("day_of_month")
        return f"{minute} {hour} {dom} * *"
    return ""


def last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def clamp_day(year: int, month: int, day: int) -> int:
    return min(day, last_day_of_month(year, month))


def _aware(tz: ZoneInfo, year, month, day, hour, minute) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=tz)


def next_from_cron(expr: str, tz: ZoneInfo, n: int, start: datetime) -> list[datetime]:
    sets = parse_cron_sets(expr)
    if sets is None:
        return []
    t = start.replace(second=0, microsecond=0) + timedelta(minutes=1)
    found: list[datetime] = []
    limit = start + timedelta(days=400)
    steps = 0
    while t <= limit and len(found) < n and steps < 600_000:
        if cron_matches(t, sets):
            found.append(t)
        t += timedelta(minutes=1)
        steps += 1
    return found


def next_daily(tz, hour, minute, n, start) -> list[datetime]:
    t = start.replace(second=0, microsecond=0)
    candidate = t.replace(hour=hour, minute=minute)
    if candidate <= start:
        candidate += timedelta(days=1)
    slots = []
    while len(slots) < n:
        slots.append(candidate)
        candidate += timedelta(days=1)
    return slots


def next_weekdays(tz, hour, minute, n, start) -> list[datetime]:
    slots = []
    d = start.date()
    for _ in range(400):
        candidate = _aware(tz, d.year, d.month, d.day, hour, minute)
        if candidate > start and candidate.weekday() < 5:
            slots.append(candidate)
            if len(slots) >= n:
                break
        d += timedelta(days=1)
    return slots


def next_weekly(tz, hour, minute, dow: int, n, start) -> list[datetime]:
    slots = []
    d = start.date()
    for _ in range(400):
        candidate = _aware(tz, d.year, d.month, d.day, hour, minute)
        if candidate > start and cron_dow(candidate) == dow:
            slots.append(candidate)
            if len(slots) >= n:
                break
        d += timedelta(days=1)
    return slots


def next_monthly(tz, hour, minute, mode: str, day: int | None, n, start) -> list[datetime]:
    slots = []
    y, m = start.year, start.month
    for _ in range(36):
        last = last_day_of_month(y, m)
        if mode == MONTHLY_LAST:
            use_day = last
        else:
            use_day = clamp_day(y, m, int(day or 1))
        candidate = _aware(tz, y, m, use_day, hour, minute)
        if candidate > start:
            slots.append(candidate)
            if len(slots) >= n:
                break
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
    return slots


def format_slot(dt: datetime, extra: str = "") -> str:
    base = dt.strftime("%Y-%m-%d %H:%M")
    return f"{base} {extra}".strip() if extra else base


def compute_slot_datetimes(
    data: dict, *, start: datetime, count: int = 3
) -> tuple[list[datetime], dict]:
    """Próximas ventanas estrictamente posteriores a start (zona del plan)."""
    kind = data.get("schedule_kind")
    tzinfo, tz_name = resolve_timezone(data.get("timezone") or "")
    if tzinfo is None:
        return [], {
            "ok": False,
            "error_code": "schedule_timezone_invalid",
            "user_message": err.MSG_TIMEZONE_INVALID,
            "timezone": "",
        }
    local_start = start.astimezone(tzinfo) if start.tzinfo else start.replace(tzinfo=tzinfo)
    extras: list[str] = []
    slots_dt: list[datetime] = []

    if kind == KIND_CRON:
        ok, msg = validate_cron_expr(data.get("cron_expr") or "")
        if not ok:
            return [], {
                "ok": False,
                "error_code": "schedule_cron_invalid",
                "user_message": err.MSG_CRON_INVALID,
                "timezone": tz_name,
            }
        slots_dt = next_from_cron(data["cron_expr"].strip(), tzinfo, count, local_start)
    else:
        parsed = parse_time_local(data.get("time_local") or "")
        if parsed is None:
            return [], {
                "ok": False,
                "error_code": "validation_form",
                "user_message": "Indique la hora local (HH:MM).",
                "timezone": tz_name,
            }
        hour, minute = parsed
        if kind == KIND_DAILY:
            slots_dt = next_daily(tzinfo, hour, minute, count, local_start)
        elif kind == KIND_WEEKDAYS:
            slots_dt = next_weekdays(tzinfo, hour, minute, count, local_start)
            extras = [DOW_LABELS[cron_dow(s)] for s in slots_dt]
        elif kind == KIND_WEEKLY:
            try:
                dow = int(data.get("day_of_week"))
            except (TypeError, ValueError):
                return [], {
                    "ok": False,
                    "error_code": "validation_form",
                    "user_message": "Seleccione el día de la semana.",
                    "timezone": tz_name,
                }
            slots_dt = next_weekly(tzinfo, hour, minute, dow, count, local_start)
            extras = [DOW_LABELS.get(dow, "") for _ in slots_dt]
        elif kind == KIND_MONTHLY:
            mode = data.get("monthly_mode") or MONTHLY_LAST
            day = data.get("day_of_month")
            if mode == MONTHLY_SPECIFIC:
                try:
                    day = int(day)
                except (TypeError, ValueError):
                    return [], {
                        "ok": False,
                        "error_code": "validation_form",
                        "user_message": "Indique el día del mes (1–31).",
                        "timezone": tz_name,
                    }
            slots_dt = next_monthly(tzinfo, hour, minute, mode, day, count, local_start)
            if mode == MONTHLY_LAST:
                extras = ["último" for _ in slots_dt]
            else:
                wanted = int(day)
                extras = ["(ajustado)" if s.day < wanted else "" for s in slots_dt]
        else:
            return [], {
                "ok": False,
                "error_code": "validation_form",
                "user_message": "Seleccione una frecuencia.",
                "timezone": tz_name,
            }
    return slots_dt, {
        "ok": True,
        "error_code": None,
        "user_message": "",
        "timezone": tz_name,
        "extras": extras,
    }


def preview_slots(data: dict, *, now: datetime | None = None, count: int = 3) -> dict:
    tzinfo, _tz_name = resolve_timezone(data.get("timezone") or "")
    if tzinfo is None:
        return {
            "ok": False,
            "error_code": "schedule_timezone_invalid",
            "slots": [],
            "user_message": err.MSG_TIMEZONE_INVALID,
        }
    start = now.astimezone(tzinfo) if now else datetime.now(tzinfo)
    slots_dt, meta = compute_slot_datetimes(data, start=start, count=count)
    if not meta["ok"]:
        return {
            "ok": False,
            "error_code": meta["error_code"],
            "slots": [],
            "user_message": meta["user_message"],
        }
    extras = meta.get("extras") or []
    labels = [
        format_slot(dt, extras[i] if i < len(extras) else "")
        for i, dt in enumerate(slots_dt)
    ]
    return {
        "ok": True,
        "error_code": None,
        "slots": labels,
        "timezone": meta["timezone"],
        "user_message": "",
    }


def latest_due_slot(schedule, now: datetime, *, lookback_hours: int = 48):
    data = snapshot_from_schedule(schedule)
    tzinfo, _ = resolve_timezone(data.get("timezone") or "")
    if tzinfo is None:
        return None
    local_now = now.astimezone(tzinfo) if now.tzinfo else now.replace(tzinfo=tzinfo)
    start = local_now - timedelta(hours=lookback_hours)
    slots_dt, meta = compute_slot_datetimes(data, start=start, count=5000)
    if not meta["ok"]:
        return None
    past = [dt for dt in slots_dt if dt <= local_now]
    return past[-1] if past else None


def snapshot_from_schedule(schedule) -> dict:
    return {
        "schedule_kind": schedule.schedule_kind or KIND_DAILY,
        "time_local": schedule.time_local or "02:00",
        "day_of_week": (
            str(schedule.day_of_week) if schedule.day_of_week is not None else "1"
        ),
        "monthly_mode": schedule.monthly_mode or MONTHLY_LAST,
        "day_of_month": (
            str(schedule.day_of_month) if schedule.day_of_month is not None else "1"
        ),
        "cron_expr": schedule.cron_expr or "",
        "timezone": schedule.timezone or DEFAULT_TIMEZONE,
    }


def first_tick_label(schedule) -> str:
    if not schedule.programming_complete:
        return "Sin programación (M2)"
    result = preview_slots(snapshot_from_schedule(schedule), count=1)
    if result["ok"] and result["slots"]:
        return result["slots"][0]
    return "—"
