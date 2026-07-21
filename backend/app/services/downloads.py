"""Shared ``Content-Disposition`` header building for binary file downloads."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote


def content_disposition_headers(storage_path: str) -> dict[str, str]:
    """Recover the public filename from a ``{id}_{name}`` storage path and build
    an RFC 6266 header (ASCII fallback + UTF-8 ``filename*``, for Cyrillic names)."""
    filename = Path(storage_path).name.split("_", 1)[-1]
    ascii_fallback = filename.encode("ascii", "replace").decode("ascii").replace("?", "_")
    return {
        "Content-Disposition": (
            f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{quote(filename)}'
        )
    }
