import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.company.models import Company


class Schedule(models.Model):
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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="schedules",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_schedules",
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

    KIND_DAILY = "daily"
    KIND_WEEKDAYS = "weekdays"
    KIND_WEEKLY = "weekly"
    KIND_MONTHLY = "monthly"
    KIND_CRON = "cron"
    KIND_CHOICES = [
        (KIND_DAILY, "Diario"),
        (KIND_WEEKDAYS, "Lunes a viernes"),
        (KIND_WEEKLY, "Semanal"),
        (KIND_MONTHLY, "Mensual"),
        (KIND_CRON, "Cron"),
    ]
    MONTHLY_LAST_DAY = "last_day"
    MONTHLY_SPECIFIC = "specific"
    MONTHLY_MODE_CHOICES = [
        (MONTHLY_LAST_DAY, "Último día"),
        (MONTHLY_SPECIFIC, "Día específico"),
    ]

    schedule_kind = models.CharField(max_length=20, blank=True, default="", choices=KIND_CHOICES)
    time_local = models.CharField(max_length=5, blank=True, default="")
    day_of_week = models.SmallIntegerField(null=True, blank=True)
    monthly_mode = models.CharField(max_length=20, blank=True, default="")
    day_of_month = models.PositiveSmallIntegerField(null=True, blank=True)
    cron_expr = models.CharField(max_length=80, blank=True, default="")
    timezone = models.CharField(max_length=64, blank=True, default="America/Caracas")
    programming_saved_at = models.DateTimeField(null=True, blank=True)

    TARGET_JOB = "job"
    TARGET_PIPELINE = "pipeline"
    TARGET_MODE_CHOICES = [
        (TARGET_JOB, "Job de app"),
        (TARGET_PIPELINE, "Pipeline"),
    ]
    INPUT_WATCH = "watch"
    INPUT_ARTIFACT = "artifact"
    INPUT_NONE = "none"
    INPUT_ORIGIN_CHOICES = [
        (INPUT_WATCH, "File Watch"),
        (INPUT_ARTIFACT, "Artifact"),
        (INPUT_NONE, "Sin archivo"),
    ]

    target_mode = models.CharField(max_length=20, blank=True, default="")
    target_kind = models.CharField(max_length=32, blank=True, default="")
    target_project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduler_plans",
    )
    published_version_number = models.PositiveIntegerField(null=True, blank=True)
    target_pipeline = models.ForeignKey(
        "file_pipeline.PipelineDefinition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduler_plans",
    )
    input_origin = models.CharField(max_length=20, blank=True, default="")
    watch_id = models.CharField(max_length=220, blank=True, default="")
    artifact_ref = models.CharField(max_length=128, blank=True, default="")
    pipeline_inputs_resolved = models.BooleanField(default=False)
    target_saved_at = models.DateTimeField(null=True, blank=True)

    OVERLAP_SKIP = "skip"
    OVERLAP_QUEUE = "queue"
    OVERLAP_CANCEL = "cancel_previous"
    OVERLAP_CHOICES = [
        (OVERLAP_SKIP, "Omitir"),
        (OVERLAP_QUEUE, "Encolar detrás"),
        (OVERLAP_CANCEL, "Cancelar el anterior"),
    ]
    overlap_policy = models.CharField(
        max_length=20,
        choices=OVERLAP_CHOICES,
        default=OVERLAP_SKIP,
    )
    overlap_saved_at = models.DateTimeField(null=True, blank=True)

    TRIGGER_TIME = "time"
    TRIGGER_DEPENDENCY = "dependency"
    TRIGGER_MODE_CHOICES = [
        (TRIGGER_TIME, "Reloj"),
        (TRIGGER_DEPENDENCY, "Dependencia"),
    ]
    PARENT_JOB = "job"
    PARENT_PIPELINE = "pipeline"
    PARENT_KIND_CHOICES = [
        (PARENT_JOB, "Job de app"),
        (PARENT_PIPELINE, "Pipeline"),
    ]
    ON_SUCCEEDED = "succeeded"
    ON_ACCEPTED = "accepted"
    ON_COMPLETED = "completed"
    ON_PARENT_CHOICES = [
        (ON_SUCCEEDED, "Éxito"),
        (ON_ACCEPTED, "Aceptado (Gate)"),
        (ON_COMPLETED, "Cualquier terminal"),
    ]
    trigger_mode = models.CharField(
        max_length=20,
        choices=TRIGGER_MODE_CHOICES,
        default=TRIGGER_TIME,
    )
    parent_kind = models.CharField(max_length=20, blank=True, default="")
    parent_project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduler_child_plans",
    )
    parent_pipeline = models.ForeignKey(
        "file_pipeline.PipelineDefinition",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduler_child_plans",
    )
    on_parent = models.CharField(max_length=20, blank=True, default="")
    dependency_saved_at = models.DateTimeField(null=True, blank=True)

    CHANNEL_EMAIL = "email"
    CHANNEL_WEBHOOK = "webhook"
    CHANNEL_BOTH = "both"
    CHANNEL_CHOICES = [
        (CHANNEL_EMAIL, "Correo"),
        (CHANNEL_WEBHOOK, "Webhook"),
        (CHANNEL_BOTH, "Correo y webhook"),
    ]
    notify_enabled = models.BooleanField(default=False)
    notify_on_tick_failed = models.BooleanField(default=True)
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
        verbose_name = "Plan programado"
        verbose_name_plural = "Planes programados"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "slug"],
                name="file_scheduler_company_slug_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "slug"]),
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def programming_complete(self) -> bool:
        return self.programming_saved_at is not None

    @property
    def target_complete(self) -> bool:
        return self.target_saved_at is not None

    @property
    def overlap_configured(self) -> bool:
        return self.overlap_saved_at is not None

    @property
    def dependency_complete(self) -> bool:
        return self.dependency_saved_at is not None


class ScheduleMembership(models.Model):
    ROLE_PA = "PA"
    ROLE_ED = "ED"
    ROLE_CO = "CO"
    ROLE_GE = "GE"
    ROLE_CHOICES = [
        (ROLE_PA, "Admin de plan"),
        (ROLE_ED, "Editor"),
        (ROLE_GE, "Ejecutor"),
        (ROLE_CO, "Consulta"),
    ]
    SCHEDULE_ROLES = frozenset({ROLE_PA, ROLE_ED, ROLE_GE, ROLE_CO})

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="schedule_memberships",
    )
    role = models.CharField(max_length=2, choices=ROLE_CHOICES)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_invitations_sent",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membresía de plan"
        verbose_name_plural = "Membresías de plan"
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "user"],
                name="file_scheduler_membership_user_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["schedule", "user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} @ {self.schedule.slug} ({self.role})"


class ScheduleAuditEvent(models.Model):
    EVENT_CREATED = "schedule.created"
    EVENT_UPDATED = "schedule.updated"
    EVENT_PAUSED = "schedule.paused"
    EVENT_RESUMED = "schedule.resumed"
    EVENT_ARCHIVED = "schedule.archived"
    EVENT_TICK_ENQUEUED = "schedule.tick_enqueued"
    EVENT_TICK_SKIPPED = "schedule.tick_skipped"
    EVENT_TICK_FAILED = "schedule.tick_failed"
    EVENT_NOTIFY_SENT = "schedule.notify_sent"
    EVENT_CHOICES = [
        (EVENT_CREATED, "Creado"),
        (EVENT_UPDATED, "Actualizado"),
        (EVENT_PAUSED, "Pausado"),
        (EVENT_RESUMED, "Reanudado"),
        (EVENT_ARCHIVED, "Archivado"),
        (EVENT_TICK_ENQUEUED, "Tick encolado"),
        (EVENT_TICK_SKIPPED, "Tick omitido"),
        (EVENT_TICK_FAILED, "Tick fallido"),
        (EVENT_NOTIFY_SENT, "Aviso enviado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="schedule_audit_events",
    )
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name="audit_events",
    )
    event = models.CharField(max_length=40, choices=EVENT_CHOICES)
    payload = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_audit_events",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Evento de auditoría de plan"
        verbose_name_plural = "Eventos de auditoría de plan"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["schedule", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event} {self.schedule.slug}"


class ScheduleTick(models.Model):
    STATUS_ENQUEUED = "enqueued"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_ENQUEUED, "Encolado"),
        (STATUS_SKIPPED, "Omitido"),
        (STATUS_FAILED, "Falló"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="schedule_ticks",
    )
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name="ticks",
    )
    scheduled_for = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    error_code = models.CharField(max_length=64, blank=True, default="")
    user_message = models.CharField(max_length=400, blank=True, default="")
    correlation_id = models.CharField(max_length=64, blank=True, default="")
    job_id = models.CharField(max_length=36, blank=True, default="")
    pipeline_run_id = models.CharField(max_length=36, blank=True, default="")
    parent_job_id = models.CharField(max_length=36, blank=True, default="")
    parent_pipeline_run_id = models.CharField(max_length=36, blank=True, default="")
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tick de plan"
        verbose_name_plural = "Ticks de plan"
        ordering = ["-scheduled_for"]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "scheduled_for"],
                condition=Q(parent_job_id="") & Q(parent_pipeline_run_id=""),
                name="file_scheduler_tick_slot_uniq",
            ),
            models.UniqueConstraint(
                fields=["schedule", "parent_job_id"],
                condition=~Q(parent_job_id=""),
                name="file_scheduler_tick_parent_job_uniq",
            ),
            models.UniqueConstraint(
                fields=["schedule", "parent_pipeline_run_id"],
                condition=~Q(parent_pipeline_run_id=""),
                name="file_scheduler_tick_parent_run_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["schedule", "-scheduled_for"]),
            models.Index(fields=["company", "-scheduled_for"]),
        ]

    def __str__(self) -> str:
        return f"{self.schedule.slug} {self.scheduled_for} {self.status}"


class ScheduleNotifyDispatch(models.Model):
    KIND_TICK_FAILED = "tick_failed"
    KIND_TICK_SKIPPED = "tick_skipped"
    KIND_RUN_FAILED = "run_failed"
    KIND_CHOICES = [
        (KIND_TICK_FAILED, "Tick fallido"),
        (KIND_TICK_SKIPPED, "Tick omitido"),
        (KIND_RUN_FAILED, "Run fallido"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schedule = models.ForeignKey(
        Schedule,
        on_delete=models.CASCADE,
        related_name="notify_dispatches",
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    ref_id = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Envío de aviso de plan"
        verbose_name_plural = "Envíos de aviso de plan"
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "kind", "ref_id"],
                name="file_scheduler_notify_ref_uniq",
            ),
        ]

