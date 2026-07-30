"""Persistencia de FileMatchRules (match_rules.md)."""

from __future__ import annotations

import copy
import logging

from apps.core.services.operation_result import OperationResult
from apps.dms.source_profile.services import source_persistence_service
from apps.file_match.models import FileMatchRules, default_match_rules
from apps.file_match.profile_b.services import profile_b_persistence_service
from apps.projects.models import Project

logger = logging.getLogger(__name__)

ALLOWED_DUPLICATE = frozenset({"bucket", "fail"})


def get_or_create_rules(project: Project) -> FileMatchRules:
    version = source_persistence_service.get_or_create_draft_version(project)
    obj, _created = FileMatchRules.objects.get_or_create(
        version=version,
        defaults={"rules": default_match_rules()},
    )
    return obj


def get_rules_dict(project: Project) -> dict:
    obj = get_or_create_rules(project)
    return normalize_rules_dict(obj.rules or {})


def normalize_rules_dict(raw: dict | None) -> dict:
    base = default_match_rules()
    data = copy.deepcopy(raw or {})
    out = {**base, **data}
    out["cardinality"] = "1:1"
    out["key"] = _normalize_pairs(data.get("key") or base["key"])
    out["compare"] = _normalize_pairs(data.get("compare") or base["compare"])
    norm = {**(base["normalize"]), **(data.get("normalize") or {})}
    out["normalize"] = {
        "trim": bool(norm.get("trim", True)),
        "case_fold_keys": bool(norm.get("case_fold_keys", True)),
    }
    dup = (data.get("on_duplicate_key") or base["on_duplicate_key"]).strip()
    out["on_duplicate_key"] = dup if dup in ALLOWED_DUPLICATE else "bucket"
    verdict = {**(base["verdict"]), **(data.get("verdict") or {})}
    out["verdict"] = {
        "fail_on_only_a": bool(verdict.get("fail_on_only_a", True)),
        "fail_on_only_b": bool(verdict.get("fail_on_only_b", True)),
        "fail_on_mismatch": bool(verdict.get("fail_on_mismatch", True)),
        "fail_on_duplicate_key": bool(verdict.get("fail_on_duplicate_key", False)),
    }
    return out


def _normalize_pairs(pairs) -> list[dict]:
    result = []
    if not isinstance(pairs, list):
        return result
    for item in pairs:
        if not isinstance(item, dict):
            continue
        a = (item.get("a") or "").strip()
        b = (item.get("b") or "").strip()
        if not a and not b:
            continue
        result.append({"a": a, "b": b})
    return result


def field_names_a(project: Project) -> list[str]:
    source = source_persistence_service.get_source_dict(project)
    names = []
    for field in source.get("fields") or []:
        name = (field.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def field_names_b(project: Project) -> list[str]:
    source = profile_b_persistence_service.get_source_b_dict(project)
    names = []
    for field in source.get("fields") or []:
        name = (field.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def validate_rules_dict(
    project: Project,
    rules: dict,
    *,
    strict: bool = False,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    errors: dict[str, list[str]] = {}
    warnings: dict[str, list[str]] = {}
    key = rules.get("key") or []
    compare = rules.get("compare") or []

    for idx, pair in enumerate(key):
        if not pair.get("a") or not pair.get("b"):
            errors.setdefault("key", []).append(
                f"El par de clave #{idx + 1} debe tener campo A y campo B."
            )

    for idx, pair in enumerate(compare):
        if not pair.get("a") or not pair.get("b"):
            errors.setdefault("compare", []).append(
                f"El par a comparar #{idx + 1} debe tener campo A y campo B."
            )

    seen_key = set()
    for pair in key:
        sig = (pair.get("a"), pair.get("b"))
        if sig in seen_key and sig[0] and sig[1]:
            errors.setdefault("key", []).append("Hay pares de clave duplicados.")
            break
        seen_key.add(sig)

    a_names_in_key = [p.get("a") for p in key if p.get("a")]
    if len(a_names_in_key) != len(set(a_names_in_key)):
        errors.setdefault("key", []).append(
            "Un mismo campo A no puede repetirse en la clave compuesta."
        )
    b_names_in_key = [p.get("b") for p in key if p.get("b")]
    if len(b_names_in_key) != len(set(b_names_in_key)):
        errors.setdefault("key", []).append(
            "Un mismo campo B no puede repetirse en la clave compuesta."
        )

    names_a = set(field_names_a(project))
    names_b = set(field_names_b(project))

    def _check_side(pairs, bucket: str):
        for idx, pair in enumerate(pairs):
            a = pair.get("a") or ""
            b = pair.get("b") or ""
            if a and names_a and a not in names_a:
                msg = f"El campo A «{a}» no existe en el perfil A (par #{idx + 1})."
                if strict:
                    errors.setdefault(bucket, []).append(msg)
                else:
                    warnings.setdefault(bucket, []).append(msg)
            elif a and not names_a:
                warnings.setdefault(bucket, []).append(
                    "El perfil A aún no tiene campos definidos."
                )
            if b and names_b and b not in names_b:
                msg = f"El campo B «{b}» no existe en el perfil B (par #{idx + 1})."
                if strict:
                    errors.setdefault(bucket, []).append(msg)
                else:
                    warnings.setdefault(bucket, []).append(msg)
            elif b and not names_b:
                warnings.setdefault(bucket, []).append(
                    "El perfil B aún no tiene campos definidos."
                )

    _check_side(key, "key")
    _check_side(compare, "compare")

    if strict and not key:
        errors.setdefault("key", []).append("Defina al menos un par de clave A↔B.")

    if rules.get("on_duplicate_key") not in ALLOWED_DUPLICATE:
        errors.setdefault("on_duplicate_key", []).append(
            "Política de duplicados inválida."
        )

    # Reject unsupported MVP keys if present in raw payload extras
    for forbidden in ("tolerance", "fuzzy", "numeric_tolerance"):
        if forbidden in rules:
            errors.setdefault("rules", []).append(
                "Opciones de tolerancia/fuzzy no están soportadas en MVP."
            )
            break

    return errors, warnings


def is_rules_complete(project: Project) -> bool:
    rules = get_rules_dict(project)
    return bool(rules.get("key"))


def save_rules(
    user,
    project: Project,
    partial: dict,
    *,
    strict: bool = False,
) -> OperationResult:
    if not source_persistence_service.user_can_edit_source(user, project):
        return OperationResult.failure(
            "forbidden",
            "No tiene permiso para editar el contrato de este proyecto.",
        )
    if project.project_kind != Project.KIND_FILE_MATCH:
        return OperationResult.failure(
            "forbidden",
            "Este proyecto no es de tipo FILE MATCH.",
        )

    obj = get_or_create_rules(project)
    current = normalize_rules_dict(obj.rules or {})
    merged = {**current, **(partial or {})}
    if "key" in (partial or {}):
        merged["key"] = partial["key"]
    if "compare" in (partial or {}):
        merged["compare"] = partial["compare"]
    if "normalize" in (partial or {}):
        merged["normalize"] = {
            **current.get("normalize", {}),
            **(partial.get("normalize") or {}),
        }
    if "verdict" in (partial or {}):
        merged["verdict"] = {
            **current.get("verdict", {}),
            **(partial.get("verdict") or {}),
        }
    rules = normalize_rules_dict(merged)

    errors, warnings = validate_rules_dict(project, rules, strict=strict)
    if errors:
        return OperationResult.failure(
            "validation_form",
            "Revise los datos de las reglas de cruce.",
            errors=errors,
            warnings=warnings,
        )

    try:
        obj.rules = rules
        obj.save()
        obj.version.save(update_fields=["updated_at"])
        project.save(update_fields=["updated_at"])
    except Exception:
        logger.exception("save_rules unexpected project=%s", project.slug)
        return OperationResult.failure(
            "unexpected",
            "Ocurrió un error al guardar. Si persiste, contacte al administrador.",
        )

    return OperationResult.success(
        user_message="Reglas de cruce guardadas correctamente.",
        payload={
            "rules": rules,
            "version": obj.version,
            "warnings": warnings,
            "warning_messages": source_persistence_service.flatten_validation_messages(
                warnings
            ),
        },
    )
