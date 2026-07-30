PROFILE_A_FILE_TYPE_WHITELIST = frozenset(
    {"csv", "xlsx", "txt_delimited", "txt_fixed", "json", "xml"}
)

WHITELIST_REJECT_MESSAGE = (
    "El tipo de archivo no está permitido en FILE MATCH (perfil A). "
    "Use CSV, Excel, TXT delimitado, TXT posicional, JSON o XML."
)


def is_allowed_profile_a_file_type(code: str | None) -> bool:
    value = (code or "").strip()
    if not value:
        return True
    return value in PROFILE_A_FILE_TYPE_WHITELIST


def reject_non_whitelist_file_type(code: str | None):
    """Return OperationResult failure if code is set and outside whitelist; else None."""
    from apps.core.services.operation_result import OperationResult

    value = (code or "").strip()
    if not value or value in PROFILE_A_FILE_TYPE_WHITELIST:
        return None
    return OperationResult.failure(
        "validation_form",
        WHITELIST_REJECT_MESSAGE,
        errors={
            "file_type_code": [
                "Solo se admiten csv, xlsx, txt_delimited, txt_fixed, json o xml "
                "como archivo A."
            ]
        },
    )
