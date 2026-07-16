from dataclasses import dataclass, field


@dataclass
class OperationResult:
    ok: bool
    error_code: str | None = None
    user_message: str = ""
    errors: dict[str, list[str]] | None = None
    payload: dict = field(default_factory=dict)

    @classmethod
    def success(
        cls,
        user_message: str = "",
        payload: dict | None = None,
        **extra,
    ) -> "OperationResult":
        combined = {**(payload or {}), **extra}
        return cls(ok=True, user_message=user_message, payload=combined)

    @classmethod
    def failure(
        cls,
        error_code: str,
        user_message: str,
        errors: dict[str, list[str]] | None = None,
        **payload,
    ) -> "OperationResult":
        return cls(
            ok=False,
            error_code=error_code,
            user_message=user_message,
            errors=errors,
            payload=payload,
        )
