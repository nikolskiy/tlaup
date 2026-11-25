"""A small real ``tla2tools.jar`` for tests (design 01 T4, "Network")."""

from __future__ import annotations

import zipfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_FIXED_DATE = (2026, 1, 1, 0, 0, 0)  # the same bytes on every run, so the same digest


def make_tools_jar(dest: Path, manifest: Path | bytes, *, repl: bool = False) -> Path:
    """Write a zip with ``META-INF/MANIFEST.MF`` (the bytes as given), an empty ``tlc2/TLC.class`` and,
    with ``repl=True``, an empty ``tlc2/REPL.class``. Returns ``dest``."""
    data = manifest if isinstance(manifest, bytes) else manifest.read_bytes()
    entries = {"META-INF/MANIFEST.MF": data, "tlc2/TLC.class": b""}
    if repl:
        entries["tlc2/REPL.class"] = b""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as jar:
        for name, content in entries.items():
            jar.writestr(zipfile.ZipInfo(name, _FIXED_DATE), content)
    return dest
