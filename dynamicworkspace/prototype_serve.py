"""Sirve HTML/CSS de prototype/ solo en DEBUG (visor Simple Browser de Cursor)."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.views.decorators.clickjacking import xframe_options_exempt

_ALLOWED_SUFFIX = {".html", ".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff2"}


def _prototype_root() -> Path:
    return (Path(settings.BASE_DIR) / "prototype").resolve()


@xframe_options_exempt
def serve_prototype(request, relpath=""):
    root = _prototype_root()
    if not root.is_dir():
        raise Http404("No hay carpeta prototype/")

    relpath = (relpath or "").replace("\\", "/").lstrip("/")
    target = (root / relpath).resolve() if relpath else root
    try:
        target.relative_to(root)
    except ValueError:
        raise Http404()

    if target.is_dir():
        index = target / "index.html"
        if index.is_file():
            if relpath and not relpath.endswith("/"):
                return HttpResponseRedirect(request.path.rstrip("/") + "/")
            target = index
        else:
            raise Http404()

    if not target.is_file() or target.suffix.lower() not in _ALLOWED_SUFFIX:
        raise Http404()

    content_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(target.open("rb"), content_type=content_type or "application/octet-stream")
