INPUT_FILE_TYPE_WHITELIST = frozenset({"csv", "xlsx", "txt_delimited"})

WHITELIST_REJECT_MESSAGE = (
    "El tipo de planilla no está permitido en Reverse Studio. "
    "Use CSV, Excel o TXT delimitado."
)


def is_allowed_input_file_type(code: str | None) -> bool:
    value = (code or "").strip()
    if not value:
        return True
    return value in INPUT_FILE_TYPE_WHITELIST


def reject_non_whitelist_file_type(code: str | None):
    """Return OperationResult failure if code is set and outside whitelist; else None."""
    from apps.core.services.operation_result import OperationResult

    value = (code or "").strip()
    if not value or value in INPUT_FILE_TYPE_WHITELIST:
        return None
    return OperationResult.failure(
        "validation_form",
        WHITELIST_REJECT_MESSAGE,
        errors={
            "file_type_code": [
                "Solo se admiten csv, xlsx o txt_delimited como planilla de entrada."
            ]
        },
    )
