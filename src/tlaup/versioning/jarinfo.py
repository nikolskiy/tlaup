"""What a TLA+ tools jar says about itself, from its manifest and entries (design 12 V5). No network, no JVM."""

from __future__ import annotations

import hashlib
import re
import struct
import zipfile
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from tlaup.errors import DownloadVerificationError

if TYPE_CHECKING:
    from pathlib import Path

_MANIFEST = "META-INF/MANIFEST.MF"
_TLC = "tlc2/TLC.class"
_REPL = "tlc2/REPL.class"
_FULL_COMMIT = re.compile(r"[0-9a-f]{40}")
_CALVER_SHAPE = re.compile(r"[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]{6}")
_CHUNK = 1 << 20

# What `zipfile` and the file system raise for a damaged, truncated or odd file.
_READ_ERRORS = (
    zipfile.BadZipFile,
    OSError,
    KeyError,
    EOFError,
    ValueError,
    RuntimeError,
    NotImplementedError,
    OverflowError,
    zlib.error,
    struct.error,
)


@dataclass(frozen=True)
class JarInfo:
    sha256: str
    size: int
    commit: str | None  # X-Git-Revision, None if absent
    built_at: str | None  # Build-TimeStamp
    calver: str | None  # built_at as %Y.%m.%d.%H%M%S in UTC
    capabilities: frozenset[str]


def _refuse(
    path: Path, reason: str, hint: str = "Download it again; a proxy or a cut connection may have given something else"
) -> DownloadVerificationError:
    return DownloadVerificationError(f"{path.name} is not a TLA+ tools jar: {reason}", hint=hint)


def _unreadable(path: Path, error: Exception) -> DownloadVerificationError:
    if isinstance(error, FileNotFoundError):
        return _refuse(path, "the file is missing", "Check the path")
    if isinstance(error, (IsADirectoryError, PermissionError)):
        what = "it is a folder" if isinstance(error, IsADirectoryError) else "it cannot be read"
        return _refuse(path, what, "Check the path")
    if isinstance(error, zipfile.BadZipFile):
        return _refuse(path, "it is not a zip file, or it was cut short")
    return _refuse(path, "it is damaged or cannot be read as a zip file")


def _hash(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(_CHUNK):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def _main_attributes(data: bytes) -> dict[str, str]:
    """The main section of a manifest: CRLF, CR or LF line ends, continuation lines start with one space."""
    lines = data.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    attributes: dict[str, str] = {}
    last: str | None = None
    for line in lines:
        if not line:
            if attributes:
                break  # the first blank line ends the main section
            continue
        if line.startswith(" "):
            if last is not None:
                attributes[last] += line[1:]
            continue
        key, colon, value = line.partition(":")
        if not colon:
            last = None
            continue
        last = key.strip().lower()
        attributes[last] = value.removeprefix(" ")
    return attributes


def _calver(built_at: str) -> str | None:
    try:
        moment = datetime.fromisoformat(built_at.strip())
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        moment = moment.astimezone(UTC)
    except (ValueError, OverflowError):
        return None
    # The year is checked here, not left to the shape: strftime pads a year below 1000 to four digits on some
    # Pythons (3.15) and not on others, so the shape alone would let year 999 through there.
    if moment.year < 1000:  # the first four-digit year
        return None
    text = moment.strftime("%Y.%m.%d.%H%M%S")
    return text if _CALVER_SHAPE.fullmatch(text) else None


def read_jar(path: Path) -> JarInfo:
    """Read a jar's identity and capabilities; raise `DownloadVerificationError` if it is not a TLA+ tools jar."""
    try:
        sha256, size = _hash(path)
        with zipfile.ZipFile(path) as jar:
            bad = jar.testzip()
            if bad is not None:
                raise _refuse(path, f"damaged entry {bad}")
            names = set(jar.namelist())
            if _TLC not in names:
                raise _refuse(path, f"no {_TLC}")
            if _MANIFEST not in names:
                raise _refuse(path, f"no {_MANIFEST}")
            attributes = _main_attributes(jar.read(_MANIFEST))
    except _READ_ERRORS as error:
        raise _unreadable(path, error) from error

    revision = attributes.get("x-git-revision", "").strip().lower()
    commit = revision if _FULL_COMMIT.fullmatch(revision) else None  # anything else is as good as absent
    stamp = attributes.get("build-timestamp", "").strip()
    calver = _calver(stamp) if stamp else None
    built_at = stamp if calver is not None else None

    capabilities: set[str] = set()
    if _REPL in names:
        capabilities.add("repl")
    if built_at is not None:
        capabilities.update({"calver", "overrides_property", "no_generate_spec_te"})
    return JarInfo(sha256, size, commit, built_at, calver, frozenset(capabilities))
