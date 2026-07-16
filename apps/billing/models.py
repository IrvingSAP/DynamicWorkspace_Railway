import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    PERIOD_MONTHLY = "monthly"
    PERIOD_ANNUAL = "annual"
    PERIOD_ENTERPRISE = "enterprise"
    PERIOD_CHOICES = [
        (PERIOD_MONTHLY, "Mensual"),
        (PERIOD_ANNUAL, "Anual"),
        (PERIOD_ENTERPRISE, "Enterprise"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, default="")
    billing_period = models.CharField(max_length=20, choices=PERIOD_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Plan"
        verbose_name_plural = "Planes"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.name


class Subscription(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"
    STATUS_CANCELED = "canceled"
    STATUS_PENDING = "pending"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Activa"),
        (STATUS_EXPIRED, "Vencida"),
        (STATUS_CANCELED, "Cancelada"),
        (STATUS_PENDING, "Pendiente de pago"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.OneToOneField(
        "company.Company",
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    auto_renew = models.BooleanField(default=False)
    integrity_signature = models.CharField(max_length=128, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscriptions_updated",
    )

    class Meta:
        verbose_name = "Suscripción"
        verbose_name_plural = "Suscripciones"
        ordering = ["company__name_short"]

    def __str__(self) -> str:
        return f"{self.company.name_short} — {self.plan.code}"

    def save(self, *args, **kwargs):
        today = timezone.localdate()
        if self.end_date < today and self.status == self.STATUS_ACTIVE:
            self.status = self.STATUS_EXPIRED

        from apps.billing.services.license_service import (
            generate_signature,
            get_license_secret,
        )

        self.integrity_signature = generate_signature(
            self.start_date,
            self.end_date,
            get_license_secret(),
        )
        super().save(*args, **kwargs)


class SubscriptionContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="contacts",
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=50, blank=True, default="")
    role = models.CharField(max_length=50, blank=True, default="")

    class Meta:
        verbose_name = "Contacto de suscripción"
        verbose_name_plural = "Contactos de suscripción"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "email"],
                name="billing_unique_contact_email_per_subscription",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self):
        super().clean()
        if not self.subscription_id:
            return
        existing = SubscriptionContact.objects.filter(
            subscription_id=self.subscription_id,
        )
        if self.pk:
            existing = existing.exclude(pk=self.pk)
        if existing.count() >= 3:
            raise ValidationError(
                "Máximo 3 contactos de soporte por suscripción.",
            )


class Payment(models.Model):
    METHOD_MANUAL = "manual"
    METHOD_CARD = "card"
    METHOD_TRANSFER = "transfer"
    METHOD_STRIPE = "stripe"
    METHOD_PAYPAL = "paypal"
    METHOD_CHOICES = [
        (METHOD_MANUAL, "Manual"),
        (METHOD_CARD, "Tarjeta"),
        (METHOD_TRANSFER, "Transferencia"),
        (METHOD_STRIPE, "Stripe"),
        (METHOD_PAYPAL, "PayPal"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    reference = models.CharField(max_length=100, blank=True, default="")
    paid_at = models.DateTimeField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_created",
    )

    class Meta:
        verbose_name = "Pago"
        verbose_name_plural = "Pagos"
        ordering = ["-paid_at"]

    def __str__(self) -> str:
        return f"{self.amount} — {self.subscription.company.name_short}"
