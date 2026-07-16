from django.contrib import admin

from apps.projects.models import Project, ProjectMembership, ProjectRecordsExpandTheme


class ProjectMembershipInline(admin.TabularInline):
    model = ProjectMembership
    extra = 0
    raw_id_fields = ("user", "invited_by")


class ProjectRecordsExpandThemeInline(admin.StackedInline):
    model = ProjectRecordsExpandTheme
    extra = 0
    max_num = 1
    can_delete = True


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "company", "owner", "is_archived", "updated_at")
    list_filter = ("is_archived", "company")
    search_fields = ("name", "slug")
    raw_id_fields = ("company", "owner")
    inlines = [ProjectMembershipInline, ProjectRecordsExpandThemeInline]


@admin.register(ProjectMembership)
class ProjectMembershipAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "role", "is_active", "created_at")
    list_filter = ("role", "is_active")
    search_fields = ("project__name", "user__username")
    raw_id_fields = ("project", "user", "invited_by")


@admin.register(ProjectRecordsExpandTheme)
class ProjectRecordsExpandThemeAdmin(admin.ModelAdmin):
    list_display = ("project", "page_length", "updated_at")
    search_fields = ("project__name", "project__slug")
    raw_id_fields = ("project",)
