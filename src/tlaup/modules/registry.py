"""Module names and the registry of ``<cache>/module/`` (design 13 M1, M2).

The only code that turns a module name into a path, and the one writer and reader of ``module.json``.
A registered module is a folder ``<root>/<name>`` with a valid name and a readable ``module.json`` of
schema 1. ``<root>/.tmp/`` holds folders being built or removed, each named ``<UTC time>-<random hex>``
so that its age is read from its name; ``<root>/.lock`` is the modules lock.
"""

from __future__ import annotations

import builtins
import json
import os
import re
import secrets
import shutil
import tempfile
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import filelock

from tlaup.errors import FileOperationError, InvalidName, ModuleNotFound, StoreLocked

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

SCHEMA = 1
RECORD = "module.json"
TMP = ".tmp"
LOCK = ".lock"
TMP_AGE = timedelta(days=1)  # a guess (design README): no build takes this long, the compiler has a timeout

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
_TIME_FORMAT = "%Y%m%dT%H%M%SZ"
_TMP_NAME = re.compile(r"(\d{8}T\d{6}Z)-[0-9a-f]+")


def validate_module_name(name: str) -> str:
    """The name, if it is a valid module name (M1); ``InvalidName`` otherwise."""
    if name in (".", "..") or _NAME.fullmatch(name) is None:
        raise InvalidName(  # noqa: TRY003
            f"{name!r} is not a valid module name",
            hint="a module name starts with a letter or digit and holds only letters, digits, '.', '_' and '-', "
            "at most 64 characters",
        )
    return name


@dataclass(frozen=True)
class RegisteredModule:
    name: str
    path: Path  # <cache>/module/<name>
    built_at: str  # UTC, ISO 8601 with Z
    source: str  # the resolved source folder, as given to build_module
    javac: str | None  # "25.0.5"; None with no Java sources or an unread version
    release: int | None  # None with no Java sources
    built_against: str | None  # "rolling@bc1b506...", None with no Java sources
    override_classes: tuple[str, ...]


def _cannot(action: str, path: Path, error: OSError) -> FileOperationError:
    return FileOperationError(f"cannot {action} {path}: {error.strerror or error}")


def write_record(folder: Path, module: RegisteredModule) -> None:
    """Write ``folder/module.json`` atomically: a file beside it, then ``os.replace``. ``module.path`` is not stored."""
    data = {
        "schema": SCHEMA,
        "name": module.name,
        "built_at": module.built_at,
        "source": module.source,
        "javac": module.javac,
        "release": module.release,
        "built_against": module.built_against,
        "override_classes": list(module.override_classes),
    }
    path = folder / RECORD
    tmp: str | None = None
    try:
        handle, tmp = tempfile.mkstemp(dir=folder, prefix=f".{RECORD}.", suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(json.dumps(data, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        Path(tmp).replace(path)
    except OSError as error:
        if tmp is not None:
            with suppress(OSError):
                Path(tmp).unlink()
        raise _cannot("write", path, error) from error


def _optional(data: dict[str, Any], key: str, kind: type) -> Any:
    value = data[key]
    if value is not None and (not isinstance(value, kind) or isinstance(value, bool)):
        message = f"{key} is not a {kind.__name__}"
        raise ValueError(message)
    return value


def read_record(folder: Path) -> RegisteredModule | None:
    """The module in ``folder``: None unless its ``module.json`` is readable, of schema 1 and names this folder."""
    try:
        data = json.loads((folder / RECORD).read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("name") != folder.name:
            return None
        classes = data["override_classes"]
        if not isinstance(classes, list) or not all(isinstance(item, str) for item in classes):
            return None
        built_at, source = data["built_at"], data["source"]
        if not isinstance(built_at, str) or not isinstance(source, str):
            return None
        return RegisteredModule(
            name=folder.name,
            path=folder,
            built_at=built_at,
            source=source,
            javac=_optional(data, "javac", str),
            release=_optional(data, "release", int),
            built_against=_optional(data, "built_against", str),
            override_classes=tuple(classes),
        )
    except (OSError, ValueError, KeyError):
        return None


def _tmp_time(name: str) -> datetime | None:
    match = _TMP_NAME.fullmatch(name)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), _TIME_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return None


def _remove_tree(path: Path) -> None:
    """Delete a file or a folder; what cannot be deleted stays."""
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path, ignore_errors=True)
    else:
        with suppress(OSError):
            path.unlink()


class Registry:
    """The registered modules under ``root`` (``AppPaths.modules``); ``now`` names the entries of ``.tmp/``."""

    def __init__(self, root: Path, *, now: Callable[[], datetime]) -> None:
        self.root = root
        self.tmp = root / TMP
        self._now = now
        self._lock_file = root / LOCK
        self._lock = filelock.FileLock(self._lock_file)

    # ------------------------------------------------------------------ reads: no lock

    def list(self) -> builtins.list[RegisteredModule]:
        """The registered modules, sorted by name in Python's string order (M2; row M18)."""
        try:
            entries = sorted(self.root.iterdir(), key=lambda entry: entry.name)
            root = self.root.resolve()
        except OSError:
            return []
        found: builtins.list[RegisteredModule] = []
        for entry in entries:
            if _NAME.fullmatch(entry.name) is None or not entry.is_dir() or entry.resolve().parent != root:
                continue  # an invalid name, a file, or a link out of the root (the second check of path_of)
            module = read_record(entry)
            if module is not None:
                found.append(module)
        return found

    def path_of(self, name: str) -> Path:
        """``<root>/<name>`` for a valid name, checked a second time on the resolved path (M1)."""
        validate_module_name(name)
        path = self.root / name
        if path.resolve().parent != self.root.resolve():
            raise InvalidName(  # noqa: TRY003
                f"module {name!r} resolves outside {self.root}",
                hint="remove the link by hand",
            )
        return path

    # ------------------------------------------------------------------ .tmp/

    def tmp_path(self, at: datetime) -> Path:
        """A new name under ``.tmp/``, ``<UTC time>-<random hex>``; nothing is created."""
        stamp = at.astimezone(UTC).strftime(_TIME_FORMAT)
        return self.tmp / f"{stamp}-{secrets.token_hex(4)}"

    def clean_tmp(self, at: datetime) -> None:
        """Remove every entry of ``.tmp/`` older than a day at ``at``; entries without a time, and errors, are left."""
        try:
            entries = builtins.list(self.tmp.iterdir())
        except OSError:
            return
        for entry in entries:
            made = _tmp_time(entry.name)
            if made is not None and at - made > TMP_AGE:
                _remove_tree(entry)

    # ------------------------------------------------------------------ the modules lock

    @contextmanager
    def locked(self, timeout: float = 60.0) -> Iterator[None]:
        """Hold ``<root>/.lock`` for the block; ``StoreLocked`` after ``timeout`` seconds."""
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            self._lock.acquire(timeout=max(timeout, 0.0))  # never without a timeout (V11)
        except filelock.Timeout:
            raise StoreLocked(  # noqa: TRY003
                f"another tlaup is changing the modules; {self._lock_file} is locked",
                hint="wait for the other tlaup to finish and try again",
            ) from None
        except OSError as error:
            raise _cannot("create", self._lock_file, error) from error
        try:
            yield
        finally:
            self._lock.release()

    # ------------------------------------------------------------------ mutations

    def put(self, folder: Path, name: str) -> bool:
        """Move a built ``folder`` (under ``.tmp/``) into place as ``name``, under the lock; True if it replaced one.

        A module already there is moved aside into ``.tmp/`` first, since a folder cannot be renamed over
        a folder that is not empty; if the second move fails, it is moved back. The old one is then
        deleted; what cannot be deleted stays for the age rule.
        """
        target = self.path_of(name)
        with self.locked():
            replaced = read_record(target) is not None  # a registered module, as remove reads it
            aside: Path | None = None
            if target.exists() or target.is_symlink():  # anything in the way is moved aside, registered or not
                aside = self.tmp_path(self._now())
                try:
                    target.rename(aside)
                except OSError as error:
                    raise _cannot("move aside", target, error) from error  # noqa: TRY003
            try:
                folder.rename(target)
            except OSError as error:
                if aside is not None:
                    with suppress(OSError):
                        aside.rename(target)
                raise _cannot("move into place", folder, error) from error  # noqa: TRY003
        if aside is not None:
            _remove_tree(aside)
        return replaced

    def remove(self, name: str) -> None:
        """Unregister ``name``: one move into ``.tmp/``, then deletion there."""
        path = self.path_of(name)
        if not self.root.is_dir():
            raise _not_registered(name)
        with self.locked():
            if not path.is_dir() or read_record(path) is None:
                raise _not_registered(name)
            aside = self.tmp_path(self._now())
            try:
                self.tmp.mkdir(parents=True, exist_ok=True)
                path.rename(aside)
            except OSError as error:
                raise _cannot("move", path, error) from error
        _remove_tree(aside)


def _not_registered(name: str) -> ModuleNotFound:
    return ModuleNotFound(f"module {name!r} is not registered", hint="run `tlaup module list`")
