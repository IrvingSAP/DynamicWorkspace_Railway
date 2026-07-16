import uuid
from datetime import datetime

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.company.models import Company


class UserProfile(models.Model):
    USER_ADMIN = "UA"
    USER_SYSTEM = "US"
    USER_FINAL = "UF"

    USER_TYPE_CHOICES = [
        (USER_ADMIN, "User Admin"),
        (USER_SYSTEM, "User System"),
        (USER_FINAL, "User Final"),
    ]

    STATUS_ACTIVE = "A"
    STATUS_INACTIVE = "I"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Activo"),
        (STATUS_INACTIVE, "Inactivo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        related_name="user_profiles",
    )
    user_type = models.CharField(max_length=2, choices=USER_TYPE_CHOICES, default=USER_FINAL)
    email_confirmed = models.BooleanField(default=False)
    email_confirm_code = models.CharField(max_length=6, null=True, blank=True)
    email_confirm_exp = models.DateTimeField(null=True, blank=True)
    totp_secret = models.CharField(max_length=64, null=True, blank=True)
    tfa_verified = models.BooleanField(default=False)
    last_totp_reset = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    locked_until = models.DateTimeField(null=True, blank=True)
    primer_acceso_completado = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_profiles",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_profiles",
    )

    class Meta:
        verbose_name = "Perfil de usuario"
        verbose_name_plural = "Perfiles de usuario"

    def __str__(self) -> str:
        return f"{self.user.username} ({self.user_type})"

    @property
    def is_security_complete(self) -> bool:
        return bool(
            self.email_confirmed
            and self.tfa_verified
            and self.totp_secret
        )

    @property
    def is_active_account(self) -> bool:
        if self.status != self.STATUS_ACTIVE:
            return False
        if self.locked_until and self.locked_until > timezone.now():
            return False
        return True

    @property
    def is_onboarding_user(self) -> bool:
        return not self.email_confirmed and not self.tfa_verified
