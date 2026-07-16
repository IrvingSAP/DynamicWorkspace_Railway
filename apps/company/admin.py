from django.contrib import admin

from apps.company.models import Company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name_short", "name_long", "is_active", "created_at")
    search_fields = ("name_short", "name_long")
    list_filter = ("is_active",)
