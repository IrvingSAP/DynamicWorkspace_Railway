"""Constantes de ejecución (transform_execution.md)."""

from datetime import timedelta

PREVIEW_ROW_LIMIT = 100
SYNC_MAX_BYTES = 50 * 1024 * 1024
DOWNLOAD_TTL = timedelta(days=7)
DOWNLOAD_KINDS = frozenset({"output", "report", "errors"})
