PHASE_MVP = "mvp"
PHASE_2 = "phase_2"
PHASE_3 = "phase_3"

PHASE_CHOICES = [
    (PHASE_MVP, "MVP"),
    (PHASE_2, "Fase 2"),
    (PHASE_3, "Fase 3"),
]

PHASE_2_ONLY_CHOICES = [
    (PHASE_MVP, "MVP"),
    (PHASE_2, "Fase 2"),
]

APPLIES_START = "start"
APPLIES_END = "end"
APPLIES_BOTH = "both"

APPLIES_TO_CHOICES = [
    (APPLIES_START, "Inicio"),
    (APPLIES_END, "Fin"),
    (APPLIES_BOTH, "Ambos"),
]

ERROR_PHASE_PARSE = "parse"
ERROR_PHASE_MAP = "map"
ERROR_PHASE_TRANSFORM = "transform"
ERROR_PHASE_WRITE = "write"
ERROR_PHASE_JOB = "job"

ERROR_PHASE_CHOICES = [
    (ERROR_PHASE_PARSE, "Parseo"),
    (ERROR_PHASE_MAP, "Mapeo"),
    (ERROR_PHASE_TRANSFORM, "Transformación"),
    (ERROR_PHASE_WRITE, "Escritura"),
    (ERROR_PHASE_JOB, "Job"),
]

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

SEVERITY_CHOICES = [
    (SEVERITY_ERROR, "Error"),
    (SEVERITY_WARNING, "Advertencia"),
]
