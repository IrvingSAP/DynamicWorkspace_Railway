import uuid

from django.conf import settings
from django.db import models

from apps.company.models import Company

SCOPE_JOBS_RUN = "jobs:run"
SCOPE_JOBS_READ = "jobs:read"
SCOPE_JOBS_CANCEL = "jobs:cancel"
SCOPE_PIPELINE_RUN = "pipeline:run"
SCOPE_ARTIFACTS_DOWNLOAD = "artifacts:download"

ALL_SCOPES = [
    SCOPE_JOBS_RUN,
    SCOPE_JOBS_READ,
    SCOPE_JOBS_CANCEL,
    SCOPE_PIPELINE_RUN,
    SCOPE_ARTIFACTS_DOWNLOAD,
]

SCOPE_LABELS = {
    SCOPE_JOBS_RUN: "Ejecutar jobs (kind suelto)",
    SCOPE_JOBS_READ: "Consultar jobs y listado",
    SCOPE_JOBS_CANCEL: "Cancelar jobs en curso",
    SCOPE_PIPELINE_RUN: "Ejecutar pipeline publicado",
    SCOPE_ARTIFACTS_DOWNLOAD: "Descargar informe / archivo",
}

ENV_SANDBOX = "sandbox"
ENV_PROD = "prod"
ENV_CHOICES = [
    (ENV_SANDBOX, "Sandbox"),
    (ENV_PROD, "Producción"),
]

STATUS_ACTIVE = "active"
STATUS_REVOKED = "revoked"
STATUS_CHOICES = [
    (STATUS_ACTIVE, "Activo"),
    (STATUS_REVOKED, "Revocado"),
]


class ApiClient(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="api_clients",
    )
    code = models.SlugField(max_length=64)
    name = models.CharField(max_length=150, blank=True, default="")
    description = models.TextField(blank=True, default="")
    environment = models.CharField(max_length=16, choices=ENV_CHOICES, default=ENV_SANDBOX)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    scopes = models.JSONField(default=list)
    public_id = models.CharField(max_length=16, unique=True)
    secret_hash = models.CharField(max_length=64)
    key_hint = models.CharField(max_length=8, blank=True, default="")
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_clients_created",
    )
    webhook_url = models.URLField(max_length=500, blank=True, default="")
    webhook_secret = models.CharField(max_length=128, blank=True, default="")
    webhook_secret_hint = models.CharField(max_length=8, blank=True, default="")
    webhook_events = models.JSONField(default=list)
    webhook_enabled = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Cliente API"
        verbose_name_plural = "Clientes API"
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "code"],
                name="platform_api_unique_code_per_company",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.company_id})"

    @property
    def is_usable(self) -> bool:
        return self.status == STATUS_ACTIVE and bool(self.company_id) and self.company.is_active

    def has_scope(self, scope: str) -> bool:
        return scope in (self.scopes or [])


ACTION_CREATED = "created"
ACTION_UPDATED = "updated"
ACTION_KEY_ROTATED = "key_rotated"
ACTION_REVOKED = "revoked"
ACTION_KEY_REVEALED = "key_revealed"

ACTION_CHOICES = [
    (ACTION_CREATED, "Alta"),
    (ACTION_UPDATED, "Cambio de configuración"),
    (ACTION_KEY_ROTATED, "Rotación de key"),
    (ACTION_REVOKED, "Revocación"),
    (ACTION_KEY_REVEALED, "Key mostrada (un uso)"),
]


class ApiClientAuditEvent(models.Model):
    """Trazabilidad append-only del ciclo de vida del cliente de máquina."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="api_client_audit_events",
    )
    client = models.ForeignKey(
        ApiClient,
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    action = models.CharField(max_length=32, choices=ACTION_CHOICES)
    summary = models.CharField(max_length=240)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_client_audit_events",
    )
    ip_address = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=256, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento de auditoría API"
        verbose_name_plural = "Eventos de auditoría API"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "-created_at"], name="pa_audit_company_at"),
            models.Index(fields=["client", "-created_at"], name="pa_audit_client_at"),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.client_id} {self.created_at}"


DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DEFAULT_RATE_PER_MINUTE = 60
DEFAULT_ARTIFACT_TTL_HOURS = 24
DEFAULT_ALLOWED_EXTENSIONS = [".txt", ".csv", ".tsv", ".xlsx", ".xls", ".xml", ".json"]


class ApiProcessPolicy(models.Model):
    """Reglas de integridad HTTP por compañía (módulo 1b)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="api_process_policy",
    )
    max_upload_bytes = models.PositiveIntegerField(default=DEFAULT_MAX_UPLOAD_BYTES)
    rate_per_minute = models.PositiveIntegerField(default=DEFAULT_RATE_PER_MINUTE)
    artifact_ttl_hours = models.PositiveIntegerField(default=DEFAULT_ARTIFACT_TTL_HOURS)
    allowed_extensions = models.JSONField(default=list)
    webhook_host_allowlist = models.JSONField(default=list)
    require_published = models.BooleanField(default=True)
    dry_run_counts_in_dashboard = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="api_process_policies_updated",
    )

    class Meta:
        verbose_name = "Política de proceso API"
        verbose_name_plural = "Políticas de proceso API"

    def __str__(self) -> str:
        return f"API policy {self.company_id}"

    def extension_list(self) -> list[str]:
        raw = self.allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS
        return [str(item).lower() if str(item).startswith(".") else f".{item}".lower() for item in raw]

    def webhook_hosts(self) -> list[str]:
        return [str(item).strip().lower() for item in (self.webhook_host_allowlist or []) if str(item).strip()]


class ApiIdempotencyRecord(models.Model):
    """Replay de POST /jobs/run por cliente + Idempotency-Key."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="api_idempotency_records",
    )
    client = models.ForeignKey(
        ApiClient,
        on_delete=models.CASCADE,
        related_name="idempotency_records",
    )
    key = models.CharField(max_length=128)
    request_hash = models.CharField(max_length=64)
    job_id = models.UUIDField()
    envelope = models.JSONField(default=dict)
    user_message = models.CharField(max_length=240, blank=True, default="")
    http_status = models.PositiveSmallIntegerField(default=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de idempotencia API"
        verbose_name_plural = "Registros de idempotencia API"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "client", "key"],
                name="platform_api_unique_idempotency_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.client_id} {self.key}"


EVENT_JOB_COMPLETED = "job.completed"
EVENT_JOB_FAILED = "job.failed"
EVENT_JOB_CANCELLED = "job.cancelled"

WEBHOOK_EVENTS = [
    EVENT_JOB_COMPLETED,
    EVENT_JOB_FAILED,
    EVENT_JOB_CANCELLED,
]

WEBHOOK_EVENT_LABELS = {
    EVENT_JOB_COMPLETED: "Job completado",
    EVENT_JOB_FAILED: "Job fallido",
    EVENT_JOB_CANCELLED: "Job cancelado",
}

DELIVERY_PENDING = "pending"
DELIVERY_DELIVERED = "delivered"
DELIVERY_FAILED = "failed"
DELIVERY_CHOICES = [
    (DELIVERY_PENDING, "Pendiente"),
    (DELIVERY_DELIVERED, "Entregado"),
    (DELIVERY_FAILED, "Agotado"),
]


class ApiWebhookDelivery(models.Model):
    """Intento de POST al callback del cliente (HMAC, sin cuerpo de archivo)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="api_webhook_deliveries",
    )
    client = models.ForeignKey(
        ApiClient,
        on_delete=models.CASCADE,
        related_name="webhook_deliveries",
    )
    event = models.CharField(max_length=32)
    job_id = models.UUIDField()
    payload = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=DELIVERY_CHOICES, default=DELIVERY_PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    response_status = models.PositiveSmallIntegerField(null=True, blank=True)
    last_error = models.CharField(max_length=240, blank=True, default="")
    next_retry_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Entrega webhook API"
        verbose_name_plural = "Entregas webhook API"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "next_retry_at"], name="pa_wh_retry"),
            models.Index(fields=["client", "-created_at"], name="pa_wh_client_at"),
        ]

    def __str__(self) -> str:
        return f"{self.event} {self.job_id} {self.status}"
