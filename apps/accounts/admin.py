from django.contrib import admin

from apps.accounts.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "company",
        "user_type",
        "email_confirmed",
        "tfa_verified",
        "status",
    )
    list_filter = ("user_type", "email_confirmed", "tfa_verified", "status")
    search_fields = ("user__username", "user__email", "company__name_short")
    raw_id_fields = ("user", "company")
