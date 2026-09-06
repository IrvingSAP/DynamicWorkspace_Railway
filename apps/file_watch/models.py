import uuid

from django.conf import settings
from django.db import models

from apps.company.models import Company


class Watch(models.Model):
    VISIBILITY_COMPANY = "company"
    VISIBILITY_MEMBERS_ONLY = "members_only"
    VISIBILITY_CHOICES = [
        (VISIBILITY_MEMBERS_ONLY, "Privado"),
        (VISIBILITY_COMPANY, "Público"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_INACTIVE = "inactive"
    STATUS_ARCHIVED = "archived"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Activo"),
        (STATUS_IN_PROGRESS, "En proceso"),
        (STATUS_INACTIVE, "Inactivo"),
        (STATUS_ARCHIVED, "Archivado"),
    ]

    SOURCE_SFTP = "sftp"
    SOURCE_MANAGED_FOLDER = "managed_folder"
    SOURCE_API_PUSH = "api_push"
    SOURCE_KIND_CHOICES = [
        (SOURCE_SFTP, "SFTP"),
        (SOURCE_MANAGED_FOLDER, "Carpeta gestionada"),
        (SOURCE_API_PUSH, "API / push"),
    ]

    AFTER_LEAVE = "leave"
    AFTER_MARK = "mark"
    AFTER_DELETE_REMOTE = "delete_remote"
    AFTER_MOVE_PROCESSED = "move_processed"
    AFTER_DELETE = "delete"
    AFTER_DETECT_CHOICES = [
        (AFTER_LEAVE, "Dejar"),
        (AFTER_MARK, "Marcar"),
        (AFTER_DELETE_REMOTE, "Borrar remoto"),
        (AFTER_MOVE_PROCESSED, "Mover a procesados"),
        (AFTER_DELETE, "Borrar"),
    ]

    PICK_FIFO = "fifo"
    PICK_LIFO = "lifo"
    PICK_CHOICES = [
        (PICK_FIFO, "FIFO"),
        (PICK_LIFO, "LIFO"),
    ]

    ROUTE_JOB = "job"
    ROUTE_PIPELINE = "pipeline"
    ROUTE_DEFER = "defer"
    ROUTE_MODE_CHOICES = [
        (ROUTE_JOB, "Job de app"),
        (ROUTE_PIPELINE, "Pipeline"),
        (ROUTE_DEFER, "Diferir"),
    ]

    FIRE_ON_ARRIVAL = "on_arrival"
    FIRE_PENDING_ONLY = "pending_only"
    FIRE_MODE_CHOICES = [
        (FIRE_ON_ARRIVAL, "Al llegar"),
        (FIRE_PENDING_ONLY, "Solo pendiente"),
    ]

    DUP_SKIP = "skip"
    DUP_ALLOW = "allow"
    DUP_REPLACE_PENDING = "replace_pending"
    DUP_POLICY_CHOICES = [
        (DUP_SKIP, "Omitir"),
        (DUP_ALLOW, "Permitir"),
        (DUP_REPLACE_PENDING, "Sustituir pendiente"),
    ]

    CHANNEL_EMAIL = "email"
    CHANNEL_WEBHOOK = "webhook"
    CHANNEL_BOTH = "both"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Correo"),
        (CHANNEL_WEBHOOK, "Webhook"),
        (CHANNEL_BOTH, "Correo y webhook"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="watches",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_watches",
    )
    visibility = models.CharField(
        max_length=20,
        choices=VISIBILITY_CHOICES,
        default=VISIBILITY_MEMBERS_ONLY,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_IN_PROGRESS,
    )

    # M2 — source
    source_kind = models.CharField(max_length=32, blank=True, default="", choices=SOURCE_KIND_CHOICES)
    filename_pattern = models.CharField(max_length=200, blank=True, default="*")
    sftp_host = models.CharField(max_length=255, blank=True, default="")
    sftp_port = models.PositiveIntegerField(null=True, blank=True)
    sftp_username = models.CharField(max_length=128, blank=True, default="")
    sftp_secret_ref = models.CharField(max_length=128, blank=True, default="")
    sftp_remote_path = models.CharField(max_length=500, blank=True, default="")
    poll_interval_sec = models.PositiveIntegerField(null=True, blank=True)
    after_detect = models.CharField(max_length=32, blank=True, default="", choices=AFTER_DETECT_CHOICES)
    folder_rel_path = models.CharField(max_length=500, blank=True, default="")
    accept_multipart = models.BooleanField(default=True)
    accept_storage_ref = models.BooleanField(default=False)
    push_token = models.CharField(max_length=128, blank=True, default="")
    push_token_hint = models.CharField(max_length=16, blank=True, default="")
    source_saved_at = models.DateTimeField(null=True, blank=True)
    source_last_test_ok = models.BooleanField(null=True, blank=True)

    # M3 — intake policy
    settle_seconds = models.PositiveIntegerField(default=5)
    max_bytes = models.BigIntegerField(default=104857600)
    pending_pick_policy = models.CharField(
        max_length=8,
        choices=PICK_CHOICES,
        default=PICK_FIFO,
    )
    retain_consumed_days = models.PositiveIntegerField(default=90)
    intake_policy_saved_at = models.DateTimeField(null=True, blank=True)

    # M4 — route
    route_mode = models.CharField(max_length=20, blank=True, default="", choices=ROUTE_MODE_CHOICES)
    route_kind = models.CharField(max_length=32, blank=True, default="")
    route_project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="watch_routes",
    )
    route_pipeline = models.ForeignKey(
        "file_pipeline.PipelineDefinition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="watch_routes",
    )
    route_saved_at = models.DateTimeField(null=True, blank=True)

    # M5 — fire
    fire_mode = models.CharField(max_length=20, blank=True, default="", choices=FIRE_MODE_CHOICES)
    fire_saved_at = models.DateTimeField(null=True, blank=True)

    # M6 — idempotency
    dup_policy = models.CharField(
        max_length=20,
        choices=DUP_POLICY_CHOICES,
        default=DUP_SKIP,
    )
    dup_window_days = models.PositiveIntegerField(default=365)
    retry_max = models.PositiveIntegerField(default=3)
    retry_backoff_sec = models.PositiveIntegerField(default=60)
    quota_max_pending = models.PositiveIntegerField(default=50)
    quota_max_arrivals_per_day = models.PositiveIntegerField(default=200)
    quota_max_bytes_per_day = models.BigIntegerField(default=0)
    idempotency_saved_at = models.DateTimeField(null=True, blank=True)

    # M9 — notify
    notify_enabled = models.BooleanField(default=False)
    notify_on_intake_failed = models.BooleanField(default=True)
    notify_on_fire_failed = models.BooleanField(default=True)
    notify_on_run_failed = models.BooleanField(default=True)
    notify_on_skip = models.BooleanField(default=False)
    notify_channel = models.CharField(max_length=16, blank=True, default="")
    notify_user_ids = models.JSONField(default=list, blank=True)
    notify_webhook_url = models.CharField(max_length=500, blank=True, default="")
    notify_webhook_secret = models.CharField(max_length=128, blank=True, default="")
    notify_saved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bandeja vigilada"
        verbose_name_plural = "Bandejas vigiladas"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "slug"],
                name="file_watch_company_slug_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "slug"]),
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def source_complete(self) -> bool:
        if self.source_saved_at is None or not self.source_kind:
            return False
        if self.source_kind == self.SOURCE_SFTP and self.source_last_test_ok is False:
            return False
        return True

    @property
    def route_complete(self) -> bool:
        return self.route_saved_at is not None and bool(self.route_mode)

    @property
    def fire_complete(self) -> bool:
        return self.fire_saved_at is not None and bool(self.fire_mode)

    @property
    def intake_policy_complete(self) -> bool:
        return self.intake_policy_saved_at is not None

    @property
    def idempotency_complete(self) -> bool:
        return self.idempotency_saved_at is not None

    @property
    def notify_complete(self) -> bool:
        return self.notify_saved_at is not None


class WatchMembership(models.Model):
    ROLE_PA = "PA"
    ROLE_ED = "ED"
    ROLE_CO = "CO"
    ROLE_GE = "GE"
    ROLE_CHOICES = [
        (ROLE_PA, "Admin de bandeja"),
        (ROLE_ED, "Editor"),
        (ROLE_GE, "Ejecutor"),
        (ROLE_CO, "Consulta"),
    ]
    WATCH_ROLES = frozenset({ROLE_PA, ROLE_ED, ROLE_GE, ROLE_CO})

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    watch = models.ForeignKey(
        Watch,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watch_memberships",
    )
    role = models.CharField(max_length=2, choices=ROLE_CHOICES)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="watch_invitations_sent",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membresía de bandeja"
        verbose_name_plural = "Membresías de bandeja"
        constraints = [
            models.UniqueConstraint(
                fields=["watch", "user"],
                name="file_watch_membership_user_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["watch", "user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} @ {self.watch.slug} ({self.role})"


class WatchBatch(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CLAIMED = "claimed"
    STATUS_CONSUMED = "consumed"
    STATUS_INTAKE_FAILED = "intake_failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente"),
        (STATUS_CLAIMED, "Reservado"),
        (STATUS_CONSUMED, "Consumido"),
        (STATUS_INTAKE_FAILED, "Falló intake"),
        (STATUS_SKIPPED, "Omitido"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="watch_batches",
    )
    watch = models.ForeignKey(
        Watch,
        on_delete=models.CASCADE,
        related_name="batches",
    )
    original_filename = models.CharField(max_length=500, blank=True, default="")
    content_hash = models.CharField(max_length=64, blank=True, default="")
    storage_key = models.CharField(max_length=500, blank=True, default="")
    byte_size = models.BigIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    source_kind = models.CharField(max_length=32, blank=True, default="")
    detected_at = models.DateTimeField(null=True, blank=True)
    ingested_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    consumed_by = models.CharField(max_length=128, blank=True, default="")
    error_code = models.CharField(max_length=64, blank=True, default="")
    job_id = models.CharField(max_length=36, blank=True, default="")
    pipeline_run_id = models.CharField(max_length=36, blank=True, default="")
    correlation_id = models.CharField(max_length=64, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Lote de bandeja"
        verbose_name_plural = "Lotes de bandeja"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["watch", "status", "-ingested_at"]),
            models.Index(fields=["watch", "content_hash"]),
            models.Index(fields=["company", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.watch.slug} {self.status} {self.original_filename}"


class WatchAuditEvent(models.Model):
    EVENT_CREATED = "watch.created"
    EVENT_UPDATED = "watch.updated"
    EVENT_PAUSED = "watch.paused"
    EVENT_RESUMED = "watch.resumed"
    EVENT_ARCHIVED = "watch.archived"
    EVENT_SOURCE_UPDATED = "watch.source_updated"
    EVENT_SOURCE_TESTED = "watch.source_tested"
    EVENT_PUSH_TOKEN_ROTATED = "watch.push_token_rotated"
    EVENT_ROUTE_UPDATED = "watch.route_updated"
    EVENT_FIRE_UPDATED = "watch.fire_updated"
    EVENT_INTAKE_POLICY_UPDATED = "watch.intake_policy_updated"
    EVENT_IDEMPOTENCY_UPDATED = "watch.idempotency_updated"
    EVENT_NOTIFY_UPDATED = "watch.notify_updated"
    EVENT_BATCH_INGESTED = "watch.batch_ingested"
    EVENT_BATCH_SKIPPED = "watch.batch_skipped"
    EVENT_BATCH_INTAKE_FAILED = "watch.batch_intake_failed"
    EVENT_BATCH_CLAIM = "watch.batch_claim"
    EVENT_FIRED = "watch.fired"
    EVENT_FIRE_FAILED = "watch.fire_failed"
    EVENT_FIRE_SKIPPED = "watch.fire_skipped"
    EVENT_RETRY_SCHEDULED = "watch.retry_scheduled"
    EVENT_NOTIFY_SENT = "watch.notify_sent"
    EVENT_CHOICES = [
        (EVENT_CREATED, "Creado"),
        (EVENT_UPDATED, "Actualizado"),
        (EVENT_PAUSED, "Pausado"),
        (EVENT_RESUMED, "Reanudado"),
        (EVENT_ARCHIVED, "Archivado"),
        (EVENT_SOURCE_UPDATED, "Origen actualizado"),
        (EVENT_SOURCE_TESTED, "Origen probado"),
        (EVENT_PUSH_TOKEN_ROTATED, "Token push rotado"),
        (EVENT_ROUTE_UPDATED, "Enrutado actualizado"),
        (EVENT_FIRE_UPDATED, "Disparo actualizado"),
        (EVENT_INTAKE_POLICY_UPDATED, "Política intake actualizada"),
        (EVENT_IDEMPOTENCY_UPDATED, "Idempotencia actualizada"),
        (EVENT_NOTIFY_UPDATED, "Avisos actualizados"),
        (EVENT_BATCH_INGESTED, "Lote ingerido"),
        (EVENT_BATCH_SKIPPED, "Lote omitido"),
        (EVENT_BATCH_INTAKE_FAILED, "Intake fallido"),
        (EVENT_BATCH_CLAIM, "Lote reclamado"),
        (EVENT_FIRED, "Disparado"),
        (EVENT_FIRE_FAILED, "Disparo fallido"),
        (EVENT_FIRE_SKIPPED, "Disparo omitido"),
        (EVENT_RETRY_SCHEDULED, "Reintento programado"),
        (EVENT_NOTIFY_SENT, "Aviso enviado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="watch_audit_events",
    )
    watch = models.ForeignKey(
        Watch,
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    event = models.CharField(max_length=48, choices=EVENT_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="watch_audit_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento de auditoría de bandeja"
        verbose_name_plural = "Eventos de auditoría de bandeja"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["watch", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event} {self.watch.slug}"


class WatchNotifyDispatch(models.Model):
    KIND_INTAKE_FAILED = "intake_failed"
    KIND_FIRE_FAILED = "fire_failed"
    KIND_RUN_FAILED = "run_failed"
    KIND_SKIP = "skip"
    KIND_CHOICES = [
        (KIND_INTAKE_FAILED, "Intake fallido"),
        (KIND_FIRE_FAILED, "Disparo fallido"),
        (KIND_RUN_FAILED, "Run fallido"),
        (KIND_SKIP, "Omitido"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    watch = models.ForeignKey(
        Watch,
        on_delete=models.CASCADE,
        related_name="notify_dispatches",
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    ref_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Envío de aviso de bandeja"
        verbose_name_plural = "Envíos de aviso de bandeja"
        constraints = [
            models.UniqueConstraint(
                fields=["watch", "kind", "ref_id"],
                name="file_watch_notify_ref_uniq",
            ),
        ]
