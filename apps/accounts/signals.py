from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.accounts.models import UserProfile

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return
    company = getattr(instance, "_setup_company", None)
    if company is None:
        return
    user_type = getattr(instance, "_setup_user_type", UserProfile.USER_FINAL)
    UserProfile.objects.create(
        user=instance,
        company=company,
        user_type=user_type,
        created_by=getattr(instance, "_setup_created_by", None),
    )
