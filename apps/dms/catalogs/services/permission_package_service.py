"""Helpers para PermissionPackage (system_catalogs.md)."""

from __future__ import annotations

from apps.projects.models import ProjectMembership

ROLE_CODES = frozenset(
    {
        ProjectMembership.ROLE_PA,
        ProjectMembership.ROLE_ED,
        ProjectMembership.ROLE_CO,
        ProjectMembership.ROLE_GE,
    }
)

FALLBACK_PACKAGES = [
    {
        "code": "admin",
        "name": "Admin",
        "maps_to_role": ProjectMembership.ROLE_PA,
        "permissions": [
            "view",
            "create",
            "update",
            "delete",
            "execute",
            "manage_members",
            "grant_admin",
        ],
    },
    {
        "code": "editor",
        "name": "Editor",
        "maps_to_role": ProjectMembership.ROLE_ED,
        "permissions": ["view", "create", "update"],
    },
    {
        "code": "viewer",
        "name": "Consulta",
        "maps_to_role": ProjectMembership.ROLE_CO,
        "permissions": ["view"],
    },
    {
        "code": "executor",
        "name": "Generar / ejecutar",
        "maps_to_role": ProjectMembership.ROLE_GE,
        "permissions": ["view", "execute"],
    },
    {
        "code": "view_only",
        "name": "Solo lectura",
        "maps_to_role": ProjectMembership.ROLE_CO,
        "permissions": ["view"],
    },
    {
        "code": "update_view",
        "name": "Ver y editar",
        "maps_to_role": ProjectMembership.ROLE_ED,
        "permissions": ["view", "update"],
    },
    {
        "code": "update_view_create",
        "name": "Ver, editar y crear",
        "maps_to_role": ProjectMembership.ROLE_ED,
        "permissions": ["view", "update", "create"],
    },
    {
        "code": "full_crud",
        "name": "CRUD completo",
        "maps_to_role": ProjectMembership.ROLE_ED,
        "permissions": ["view", "create", "update", "delete"],
    },
]


def list_permission_packages(*, active_only: bool = True) -> list[dict]:
    try:
        from apps.dms.models import PermissionPackage

        qs = PermissionPackage.objects.all().order_by("sort_order", "code")
        if active_only:
            qs = qs.filter(is_active=True)
        rows = list(qs)
        if rows:
            return [
                {
                    "code": row.code,
                    "name": row.name,
                    "maps_to_role": row.maps_to_role,
                    "permissions": list(row.permissions or []),
                    "description": row.description or "",
                }
                for row in rows
            ]
    except Exception:
        pass
    return [dict(item) for item in FALLBACK_PACKAGES]


def role_choices_for_ui() -> list[dict]:
    """
    Opciones UI de miembro: una por rol PA/ED/CO/GE (primer paquete activo que mapee).
    value = maps_to_role para no romper change_role / membership.
    """
    preferred = ["admin", "editor", "viewer", "executor"]
    by_role: dict[str, dict] = {}
    packages = list_permission_packages(active_only=True)
    packages.sort(
        key=lambda pkg: (
            preferred.index(pkg["code"]) if pkg.get("code") in preferred else 99,
            pkg.get("code") or "",
        )
    )
    for pkg in packages:
        role = (pkg.get("maps_to_role") or "").strip().upper()
        code = (pkg.get("code") or "").strip()
        if not code or role not in ROLE_CODES or role in by_role:
            continue
        name = pkg.get("name") or code
        by_role[role] = {
            "code": role,
            "label": f"{name} ({role})",
            "maps_to_role": role,
            "package_code": code,
        }
    if by_role:
        order = [
            ProjectMembership.ROLE_PA,
            ProjectMembership.ROLE_ED,
            ProjectMembership.ROLE_CO,
            ProjectMembership.ROLE_GE,
        ]
        return [by_role[role] for role in order if role in by_role]
    return [
        {"code": code, "label": label, "maps_to_role": code, "package_code": code}
        for code, label in ProjectMembership.ROLE_CHOICES
    ]


def resolve_role_code(raw: str) -> str | None:
    """Acepta código de rol PA/ED/CO/GE o código de paquete → maps_to_role."""
    value = (raw or "").strip()
    if not value:
        return None
    upper = value.upper()
    if upper in ROLE_CODES:
        return upper
    for pkg in list_permission_packages(active_only=True):
        if pkg.get("code") == value:
            role = (pkg.get("maps_to_role") or "").strip().upper()
            return role if role in ROLE_CODES else None
    return None


def is_valid_assignable_role(raw: str) -> bool:
    return resolve_role_code(raw) is not None
