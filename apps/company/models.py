import uuid

from django.conf import settings
from django.db import models


class Company(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name_short = models.CharField(max_length=15, unique=True)
    name_long = models.CharField(max_length=150)
    tax_id = models.CharField(max_length=50, blank=True, default="")
    address = models.CharField(max_length=255, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")
    email = models.EmailField(blank=True, default="")
    logo = models.ImageField(upload_to="company_logos/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="companies_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="companies_updated",
    )

    class Meta:
        verbose_name = "Compañía"
        verbose_name_plural = "Compañías"
        ordering = ["name_short"]

    def __str__(self) -> str:
        return self.name_short
