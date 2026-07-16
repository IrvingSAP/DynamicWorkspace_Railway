import uuid

from django.conf import settings
from django.db import models

from apps.company.models import Company


class Project(models.Model):
    KIND_WORKSPACE = "workspace"
    KIND_DMS = "dms"
    KIND_CHOICES = [
        (KIND_WORKSPACE, "Workspace (tabla)"),
        (KIND_DMS, "DMS (FilePipe)"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="projects",
    )
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220)
    description = models.TextField(blank=True, default="")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_projects",
    )
    is_archived = models.BooleanField(default=False)
    project_kind = models.CharField(
        max_length=16,
        choices=KIND_CHOICES,
        default=KIND_WORKSPACE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Proyecto"
        verbose_name_plural = "Proyectos"
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "slug"],
                name="projects_project_company_slug_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "slug"]),
            models.Index(fields=["company", "is_archived"]),
            models.Index(fields=["company", "project_kind"]),
        ]

    def __str__(self) -> str:
        return self.name


class ProjectRecordsExpandTheme(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="expand_theme",
    )

    header_bg = models.CharField(max_length=7, default="#e8eef4")
    header_color = models.CharField(max_length=7, default="#1a1d21")
    header_border = models.CharField(max_length=7, default="#c5cdd8")
    cell_border = models.CharField(max_length=7, default="#d4d9e0")
    stripe_bg = models.CharField(max_length=7, default="#f7f9fb")
    hover_bg = models.CharField(max_length=7, default="#e8eef4")

    grid_cell_border = models.BooleanField(default=True)
    layout_compact = models.BooleanField(default=True)
    row_stripe = models.BooleanField(default=True)
    row_hover = models.BooleanField(default=True)
    column_order_highlight = models.BooleanField(default=True)
    cell_nowrap = models.BooleanField(default=True)

    page_length = models.PositiveSmallIntegerField(default=25)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tema tabla expandida de registros"
        verbose_name_plural = "Temas tabla expandida de registros"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(page_length__gte=10) & models.Q(page_length__lte=100),
                name="projects_expandtheme_page_length_range",
            ),
        ]

    def __str__(self) -> str:
        return f"Tema expand — {self.project.slug}"


class ProjectMembership(models.Model):
    ROLE_PA = "PA"
    ROLE_ED = "ED"
    ROLE_CO = "CO"
    ROLE_GE = "GE"

    ROLE_CHOICES = [
        (ROLE_PA, "Admin de proyecto"),
        (ROLE_ED, "Editor"),
        (ROLE_CO, "Consulta"),
        (ROLE_GE, "Generar"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_memberships",
    )
    role = models.CharField(max_length=2, choices=ROLE_CHOICES)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="project_invitations_sent",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membresía de proyecto"
        verbose_name_plural = "Membresías de proyecto"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "user"],
                name="projects_membership_project_user_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "user", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.username} @ {self.project.slug} ({self.role})"
