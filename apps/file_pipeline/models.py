import uuid

from django.conf import settings
from django.db import models

from apps.company.models import Company


class PipelineDefinition(models.Model):
    VISIBILITY_COMPANY = "company"
    VISIBILITY_MEMBERS_ONLY = "members_only"
    VISIBILITY_CHOICES = [
        (VISIBILITY_MEMBERS_ONLY, "Privado"),
        (VISIBILITY_COMPANY, "Público"),
    ]

    STATUS_ACTIVE = "active"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_INACTIVE = "inactive"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Activo"),
        (STATUS_IN_PROGRESS, "En proceso"),
        (STATUS_INACTIVE, "Inactivo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="pipeline_definitions",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_pipelines",
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
    draft_step_labels = models.JSONField(default=list, blank=True)
    draft_steps = models.JSONField(default=list, blank=True)
    design_saved_at = models.DateTimeField(null=True, blank=True)
    current_version = models.ForeignKey(
        "PipelineVersion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pipeline"
        verbose_name_plural = "Pipelines"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "slug"],
                name="file_pipeline_def_company_slug_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "slug"]),
            models.Index(fields=["company", "status"]),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def design_complete(self) -> bool:
        labels = self.draft_step_labels or []
        steps = self.draft_steps or []
        return bool(self.design_saved_at) and (len(labels) >= 1 or len(steps) >= 1)


class PipelineMembership(models.Model):
    ROLE_PA = "PA"
    ROLE_ED = "ED"
    ROLE_CO = "CO"
    ROLE_GE = "GE"
    ROLE_CHOICES = [
        (ROLE_PA, "Admin de pipeline"),
        (ROLE_ED, "Editor"),
        (ROLE_GE, "Ejecutor"),
        (ROLE_CO, "Consulta"),
    ]
    PIPELINE_ROLES = frozenset({ROLE_PA, ROLE_ED, ROLE_GE, ROLE_CO})

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline = models.ForeignKey(
        PipelineDefinition,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pipeline_memberships",
    )
    role = models.CharField(max_length=2, choices=ROLE_CHOICES)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pipeline_invitations_sent",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membresía de pipeline"
        verbose_name_plural = "Membresías de pipeline"
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline", "user"],
                name="file_pipeline_membership_user_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["pipeline", "user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} @ {self.pipeline.slug} ({self.role})"


class PipelineVersion(models.Model):
    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Borrador"),
        (STATUS_PUBLISHED, "Publicada"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline = models.ForeignKey(
        PipelineDefinition,
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version_number = models.PositiveIntegerField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PUBLISHED,
    )
    steps = models.JSONField(default=list, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pipeline_versions_published",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Versión de pipeline"
        verbose_name_plural = "Versiones de pipeline"
        ordering = ["-version_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["pipeline", "version_number"],
                name="file_pipeline_version_number_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pipeline.slug} v{self.version_number}"


class PipelineStepKind(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_DEPRECATED = "deprecated"
    STATUS_DISABLED = "disabled"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "active"),
        (STATUS_DEPRECATED, "deprecated"),
        (STATUS_DISABLED, "disabled"),
    ]

    INPUT_CHOICES = [
        ("1", "1"),
        ("2", "2"),
        ("N", "N"),
        ("foreach", "foreach"),
    ]
    OUTPUT_CHOICES = [
        ("1", "1"),
        ("N", "N"),
        ("none", "none"),
    ]
    PHASE_CHOICES = [
        ("", "—"),
        ("A", "A"),
        ("B", "B"),
        ("C", "C"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.SlugField(max_length=64, unique=True)
    label = models.CharField(max_length=120)
    short_label = models.CharField(max_length=40, blank=True, default="")
    description = models.TextField(blank=True, default="")
    project_kind = models.CharField(max_length=64)
    runner = models.CharField(max_length=120)
    input_arity = models.CharField(max_length=16, choices=INPUT_CHOICES, default="1")
    output_arity = models.CharField(max_length=16, choices=OUTPUT_CHOICES, default="1")
    produces_file = models.BooleanField(default=True)
    pipeline_enabled = models.BooleanField(default=False)
    mvp_phase = models.CharField(max_length=1, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )
    disable_reason = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pipeline_step_kinds_updated",
    )

    class Meta:
        verbose_name = "Kind de paso de pipeline"
        verbose_name_plural = "Catálogo de pasos de pipeline"
        ordering = ["kind"]

    def __str__(self) -> str:
        return self.kind

    @property
    def short(self) -> str:
        return self.short_label or self.label

    def as_picker_dict(self) -> dict:
        return {
            "kind": self.kind,
            "label": self.label,
            "short": self.short,
            "project_kind": self.project_kind,
            "pipeline_enabled": self.pipeline_enabled,
            "status": self.status,
        }


class PipelineCompanyKindFlag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="pipeline_kind_flags",
    )
    step_kind = models.ForeignKey(
        PipelineStepKind,
        on_delete=models.CASCADE,
        related_name="company_flags",
    )
    included = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Flag compañía × kind"
        verbose_name_plural = "Flags compañía × kind"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "step_kind"],
                name="file_pipeline_company_kind_flag_uniq",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.company.name_short}:{self.step_kind.kind}={self.included}"


class PipelineRun(models.Model):
    TRIGGER_UI = "ui"
    TRIGGER_API = "api"
    TRIGGER_WATCH = "watch"
    TRIGGER_SCHEDULER = "scheduler"
    TRIGGER_DEPENDENCY = "dependency"
    TRIGGER_CHOICES = [
        (TRIGGER_UI, "UI"),
        (TRIGGER_API, "API"),
        (TRIGGER_WATCH, "Watch"),
        (TRIGGER_SCHEDULER, "Scheduler"),
        (TRIGGER_DEPENDENCY, "Dependencia"),
    ]

    STATUS_QUEUED = "queued"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "En cola"),
        (STATUS_RUNNING, "En curso"),
        (STATUS_COMPLETED, "Completado"),
        (STATUS_FAILED, "Fallido"),
        (STATUS_CANCELLED, "Cancelado"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pipeline = models.ForeignKey(
        PipelineDefinition,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    version = models.ForeignKey(
        PipelineVersion,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    trigger_source = models.CharField(
        max_length=20,
        choices=TRIGGER_CHOICES,
        default=TRIGGER_UI,
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_QUEUED,
    )
    dry_run = models.BooleanField(default=False)
    input_filename = models.CharField(max_length=255, blank=True, default="")
    input_sha256 = models.CharField(max_length=64, blank=True, default="")
    error_message = models.CharField(max_length=500, blank=True, default="")
    failed_step_order = models.PositiveIntegerField(null=True, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pipeline_runs_triggered",
    )
    correlation_id = models.CharField(max_length=64, blank=True, default="")
    idempotency_key = models.CharField(max_length=120, blank=True, default="")
    api_client_label = models.CharField(max_length=120, blank=True, default="")
    client_ip = models.CharField(max_length=45, blank=True, default="")
    user_agent = models.CharField(max_length=300, blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Corrida de pipeline"
        verbose_name_plural = "Corridas de pipeline"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["pipeline", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.pipeline.slug} {self.id}"


class PipelineStepRun(models.Model):
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_SKIPPED = "skipped"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pendiente"),
        (STATUS_RUNNING, "En curso"),
        (STATUS_COMPLETED, "Completado"),
        (STATUS_FAILED, "Fallido"),
        (STATUS_SKIPPED, "Omitido"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run = models.ForeignKey(
        PipelineRun,
        on_delete=models.CASCADE,
        related_name="steps",
    )
    order = models.PositiveIntegerField()
    kind = models.CharField(max_length=64)
    label = models.CharField(max_length=120, blank=True, default="")
    project_slug = models.CharField(max_length=220, blank=True, default="")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    app_job_id = models.CharField(max_length=64, blank=True, default="")
    error_code = models.CharField(max_length=80, blank=True, default="")
    user_message = models.CharField(max_length=500, blank=True, default="")
    skip_reason = models.CharField(max_length=80, blank=True, default="")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    artifacts = models.JSONField(default=list, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Paso de corrida"
        verbose_name_plural = "Pasos de corrida"
        ordering = ["order"]

    def __str__(self) -> str:
        return f"{self.run_id} #{self.order} {self.kind}"
