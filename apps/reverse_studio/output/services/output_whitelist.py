OUTPUT_FILE_TYPE_WHITELIST = frozenset({"txt_fixed", "json", "xml"})

WHITELIST_REJECT_MESSAGE = (
    "El tipo de layout no está permitido en Reverse Studio. "
    "Use TXT posicional, JSON o XML."
)

AUTO_ENCODING_REJECT_MESSAGE = (
    "La codificación o el final de línea no pueden ser automáticos en el layout de envío. "
    "Elija un valor explícito."
)


def is_allowed_output_file_type(code: str | None) -> bool:
    value = (code or "").strip()
    if not value:
        return True
    return value in OUTPUT_FILE_TYPE_WHITELIST


def reject_non_whitelist_file_type(code: str | None):
    from apps.core.services.operation_result import OperationResult

    value = (code or "").strip()
    if not value or value in OUTPUT_FILE_TYPE_WHITELIST:
        return None
    return OperationResult.failure(
        "validation_form",
        WHITELIST_REJECT_MESSAGE,
        errors={
            "file_type_code": [
                "Solo se admiten txt_fixed, json o xml como layout de envío."
            ]
        },
    )


def reject_auto_write_format(encoding_code: str | None, line_ending_code: str | None):
    """OUT11: escritura explícita (sin auto)."""
    from apps.core.services.operation_result import OperationResult

    enc = (encoding_code or "").strip().lower()
    le = (line_ending_code or "").strip().lower()
    errors: dict[str, list[str]] = {}
    if enc in ("auto", "detect", "auto_detect"):
        errors["encoding_code"] = ["Seleccione una codificación explícita (no automática)."]
    if le in ("auto", "detect", "auto_detect"):
        errors["line_ending_code"] = ["Seleccione un final de línea explícito (no automático)."]
    if not errors:
        return None
    return OperationResult.failure(
        "validation_form",
        AUTO_ENCODING_REJECT_MESSAGE,
        errors=errors,
    )
