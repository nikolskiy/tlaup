"""The tool store: installed builds, the pin and the store lock (design 12 V1, V2, V11).

The only code that composes a build's folder name or reads ``build.json``. Reads never lock;
every mutation requires the caller to hold the store lock and checks that it does. The step
functions (``acquire``, ``release``, ``new_tmp``, ``clean_tmp``, ``move_out``, ``delete_out``)
are the actions of ``specs/ToolStore.tla``, so each is one step and no more.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import uuid
from contextlib import contextmanager, suppress
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

import filelock

from tlaup.errors import FileOperationError, InternalError, PinnedBuildMissing, StoreLocked
from tlaup.versioning.order import ROLLING, name_key, sort_key, version_key
from tlaup.versioning.spec import format_build

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tlaup.paths import AppPaths
    from tlaup.versioning.jarinfo import JarInfo
    from tlaup.versioning.spec import VersionSpec

SCHEMA = 1
JAR = "tla2tools.jar"
RECORD = "build.json"
TMP = ".tmp"
LOCK = ".lock"
STABLE = "stable"
ID_DIGITS = 12
LOCK_FILE_AGE = timedelta(hours=1)  # a lock file under .tmp/ with no folder is removed after this (V11)

_UNSAFE = re.compile(r"[^A-Za-z0-9._]")
_SHA256 = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class Source:
    kind: str  # "github-release" in the first wave
    url: str  # the asset's download address as the release gave it; never a redirect's signed address
    asset_id: int | None
    asset_updated_at: str | None
    digest_checked: bool  # the download was compared with GitHub's digest


@dataclass(frozen=True)
class Build:
    id: str  # the folder name; opaque outside the store
    name: str  # "v1.7.4", "rolling"
    commit: str | None  # 40 hex digits, from the jar's manifest; None if the jar has none
    calver: str | None  # "2026.11.15.002146", None when the jar has no Build-TimeStamp
    built_at: str | None  # the manifest's Build-TimeStamp
    sha256: str
    size: int
    prerelease: bool
    source: Source  # where it came from
    installed_at: str  # UTC, ISO 8601 with Z
    capabilities: frozenset[str]  # 00, "What a build can do"
    path: Path  # the build's folder

    @property
    def jar(self) -> Path:
        return self.path / JAR


def build_id(name: str, sha256: str, digits: int = ID_DIGITS) -> str:
    """The first candidate id: the name made safe for any file system, ``-``, the jar's digest's first digits."""
    return f"{_UNSAFE.sub('_', name)}-{sha256[:digits]}"


def _cannot(action: str, path: Path, error: OSError) -> FileOperationError:
    return FileOperationError(f"cannot {action} {path}: {error.strerror or error}")


def _write_atomic(path: Path, text: str) -> None:
    """Write a temporary file in the same folder, then move it into place in one rename."""
    tmp: str | None = None
    try:
        handle, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        Path(tmp).replace(path)
    except OSError as error:
        if tmp is not None:
            with suppress(OSError):
                Path(tmp).unlink()
        raise _cannot("write", path, error) from error


def _write_build(folder: Path, build: Build) -> None:
    """The one writer of ``build.json``: every field of ``Build`` but ``id`` and ``path``, under a schema."""
    record = {
        "schema": SCHEMA,
        "name": build.name,
        "commit": build.commit,
        "calver": build.calver,
        "built_at": build.built_at,
        "sha256": build.sha256,
        "size": build.size,
        "prerelease": build.prerelease,
        "source": {
            "kind": build.source.kind,
            "url": build.source.url,
            "asset_id": build.source.asset_id,
            "asset_updated_at": build.source.asset_updated_at,
            "digest_checked": build.source.digest_checked,
        },
        "installed_at": build.installed_at,
        "capabilities": sorted(build.capabilities),
    }
    _write_atomic(folder / RECORD, json.dumps(record, indent=2) + "\n")


def _is(value: object, kind: type, *, optional: bool = False) -> bool:
    if value is None:
        return optional
    if kind is int and isinstance(value, bool):
        return False
    return isinstance(value, kind)


def _read_source(data: Any) -> Source | None:
    if not isinstance(data, dict):
        return None
    kind, url, checked = data.get("kind"), data.get("url"), data.get("digest_checked")
    asset_id, updated = data.get("asset_id"), data.get("asset_updated_at")
    if not (isinstance(kind, str) and isinstance(url, str) and isinstance(checked, bool)):
        return None
    if not (_is(asset_id, int, optional=True) and _is(updated, str, optional=True)):
        return None
    return Source(kind, url, asset_id, updated, checked)


def _valid_record(data: Any) -> bool:
    if not isinstance(data, dict) or not _is(data.get("schema"), int) or data["schema"] != SCHEMA:
        return False
    texts = [data.get(key) for key in ("name", "sha256", "installed_at")]
    maybe = [data.get(key) for key in ("commit", "calver", "built_at")]
    capabilities = data.get("capabilities")
    return (
        all(_is(value, str) for value in texts)
        and all(_is(value, str, optional=True) for value in maybe)
        and _SHA256.fullmatch(data["sha256"]) is not None
        and _is(data.get("size"), int)
        and _is(data.get("prerelease"), bool)
        and isinstance(capabilities, list)
        and all(_is(value, str) for value in capabilities)
    )


def _read_record(folder: Path) -> Build | None:
    """The one reader of ``build.json``: None unless it is readable and of a known schema. The jar is not looked at."""
    try:
        data: Any = json.loads((folder / RECORD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    source = _read_source(data.get("source")) if isinstance(data, dict) else None
    if source is None or not _valid_record(data):
        return None
    return Build(
        id=folder.name,
        name=data["name"],
        commit=data.get("commit"),
        calver=data.get("calver"),
        built_at=data.get("built_at"),
        sha256=data["sha256"],
        size=data["size"],
        prerelease=data["prerelease"],
        source=source,
        installed_at=data["installed_at"],
        capabilities=frozenset(data["capabilities"]),
        path=folder,
    )


def _read_build(folder: Path) -> Build | None:
    """A build: a readable ``build.json`` of a known schema and a jar beside it."""
    build = _read_record(folder)
    try:
        has_jar = build is not None and build.jar.is_file()
    except OSError:
        return None
    return build if has_jar else None


def _try_lock(lock: filelock.FileLock, timeout: float) -> bool:
    """Never wait without a timeout (V11): a second lock object in one thread would then raise RuntimeError."""
    try:
        lock.acquire(timeout=max(timeout, 0.0))
    except filelock.Timeout:
        return False
    return True


class TmpFolder:
    """A folder under ``.tmp/`` and the lock file beside it (V11), held by the tlaup that owns the folder."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock_file = path.with_name(f"{path.name}.lock")
        self._lock = filelock.FileLock(self.lock_file)

    def lock(self) -> None:
        """Create the lock file and take its lock, before the folder exists."""
        try:
            self.lock_file.parent.mkdir(parents=True, exist_ok=True)
            got = _try_lock(self._lock, 0)
        except OSError as error:
            raise _cannot("create", self.lock_file, error) from error
        if not got:
            raise StoreLocked(f"{self.lock_file} is held by another tlaup")  # noqa: TRY003

    def make(self) -> None:
        try:
            self.path.mkdir()
        except OSError as error:
            raise _cannot("create", self.path, error) from error

    def discard(self) -> None:
        """Delete the folder. What cannot be deleted stays, and a later cleanup removes it once unlocked."""
        shutil.rmtree(self.path, ignore_errors=True)

    def release(self) -> None:
        """Remove the lock file as the last thing while holding it, then release the lock."""
        if not self._lock.is_locked:
            return  # never taken: the file, if any, is another tlaup's
        with suppress(OSError):
            self.lock_file.unlink(missing_ok=True)
        self._lock.release()


class ToolStore:
    def __init__(self, paths: AppPaths, *, now: Callable[[], datetime], id_digits: int = ID_DIGITS) -> None:
        self._root = paths.tools
        self._pin = paths.pin
        self._tmp = paths.tools / TMP
        self._now = now
        self._id_digits = id_digits  # a test gives it fewer digits to make two jars agree
        self._lock_file = paths.tools / LOCK
        self._lock = filelock.FileLock(self._lock_file)  # this object's own: a second object is refused

    # ------------------------------------------------------------------ reads: no lock

    def builds(self) -> list[Build]:
        """Every folder that holds a jar and a readable ``build.json``, sorted by 02 X4."""
        try:
            entries = list(self._root.iterdir())
        except FileNotFoundError:
            return []
        except OSError as error:
            raise _cannot("read", self._root, error) from error
        found = [build for entry in entries if entry.name != TMP and (build := _read_build(entry)) is not None]
        return sorted(found, key=sort_key)

    def find(self, spec: VersionSpec) -> list[Build]:
        """The installed builds a spec names, newest first; empty when none (V2)."""
        builds = self.builds()
        if spec.name is None:
            found = builds
        elif spec.name == STABLE:
            found = _stable(builds)
        elif spec.name == ROLLING:
            found = [build for build in builds if build.name == ROLLING]
        else:
            found = [build for build in builds if build.name == spec.name]
            if not found:
                found = [build for build in builds if build.name == f"v{spec.name}"]
        if spec.commit is not None:
            commit = spec.commit
            found = [build for build in found if build.commit is not None and build.commit.startswith(commit)]
        if spec.calver is not None:
            found = [build for build in found if build.calver == spec.calver]
        if spec.sha256 is not None:
            digest = spec.sha256
            found = [build for build in found if build.sha256.startswith(digest)]
        return found

    def pinned(self) -> Build | None:
        """The pinned build; None with no pin file or an empty one; ``PinnedBuildMissing`` if it is not a build."""
        try:
            text = self._pin.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return None
        except OSError as error:
            raise _cannot("read", self._pin, error) from error
        pin = text.strip()
        if not pin:
            return None
        builds = self.builds()
        for build in builds:
            if build.id == pin:
                return build
        raise self._missing(pin, builds)

    def _missing(self, pin: str, builds: list[Build]) -> PinnedBuildMissing:
        """11 R11 step 3: the printed form and the name when the record is still there; the bare words if not."""
        folder = self._root / pin
        record = _read_record(folder) if folder.parent == self._root and pin not in {".", "..", TMP} else None
        if record is None:
            return PinnedBuildMissing(
                "the pinned build is missing",
                hint="run `tlaup tool install ...` or `tlaup tool pin ...`",
            )
        printed = format_build(record, [*builds, record])
        return PinnedBuildMissing(
            f"the pinned build {printed} is missing",
            hint=f"run `tlaup tool install {record.name}` or `tlaup tool pin ...`",
        )

    # ------------------------------------------------------------------ the store lock

    def acquire(self, timeout: float = 60.0) -> None:
        """Take the store lock, waiting at most ``timeout`` seconds; ``StoreLocked`` after that."""
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            got = _try_lock(self._lock, timeout)
        except OSError as error:
            raise _cannot("create", self._lock_file, error) from error
        if not got:
            raise StoreLocked(  # noqa: TRY003
                f"another tlaup is changing the installed tools; {self._lock_file} is locked",
                hint="wait for the other tlaup to finish and try again",
            )

    def release(self) -> None:
        self._lock.release()

    @contextmanager
    def locked(self, timeout: float = 60.0) -> Iterator[None]:
        self.acquire(timeout)
        try:
            yield
        finally:
            self.release()

    def _require_lock(self, action: str) -> None:
        if not self._lock.is_locked:
            raise InternalError(f"{action} needs the store lock, which this tlaup does not hold")  # noqa: TRY003

    # ------------------------------------------------------------------ temporary folders (V11)

    def new_tmp(self) -> TmpFolder:
        return TmpFolder(self._tmp / uuid.uuid4().hex)

    def clean_tmp(self) -> None:
        """Remove what dead tlaups left under ``.tmp/``: folders whose lock is free, old lock files alone."""
        self._require_lock("cleaning .tmp/")
        try:
            entries = list(self._tmp.iterdir())
        except FileNotFoundError:
            return
        except OSError as error:
            raise _cannot("read", self._tmp, error) from error
        for entry in entries:
            if entry.is_dir() and not entry.is_symlink():
                self._clean_folder(entry)
        for entry in entries:
            folder = entry.with_name(entry.name.removesuffix(".lock"))
            if entry.name.endswith(".lock") and entry.is_file() and not folder.exists():
                self._clean_lock_file(entry)

    def _clean_folder(self, folder: Path) -> None:
        out = TmpFolder(folder)
        if not _try_lock(out._lock, 0):
            return  # its owner is alive, however long it takes
        out.discard()
        out.release()

    def _clean_lock_file(self, lock_file: Path) -> None:
        lock = filelock.FileLock(lock_file)
        if not _try_lock(lock, 0):
            return
        try:
            changed = datetime.fromtimestamp(lock_file.stat().st_mtime, UTC)
            if self._now() - changed > LOCK_FILE_AGE:
                lock_file.unlink(missing_ok=True)
        except OSError:
            pass  # gone meanwhile, or not removable: a later cleanup tries again
        finally:
            lock.release()

    # ------------------------------------------------------------------ mutations: the caller holds the lock

    def add(  # noqa: PLR0913 (the design's signature, 12 V1)
        self, jar: Path, info: JarInfo, *, name: str, prerelease: bool, source: Source, repair: bool = False
    ) -> Build:
        """Move the temporary folder holding ``jar`` into the store, or return the build already there.

        "Already there" is the same name and the same SHA-256. With ``repair`` its jar and
        ``build.json`` are replaced first. The caller keeps the temporary folder's lock and releases it.
        """
        self._require_lock("adding a build")
        folder = jar.parent
        if folder.parent != self._tmp:
            raise InternalError(f"{jar} is not in a temporary folder of the store")  # noqa: TRY003
        for existing in self.builds():
            if existing.name == name and existing.sha256 == info.sha256:
                if not repair:
                    shutil.rmtree(folder, ignore_errors=True)
                    return existing
                build = self._build(existing.path, info, name=name, prerelease=prerelease, source=source)
                try:
                    jar.replace(existing.jar)
                except OSError as error:
                    raise _cannot("replace", existing.jar, error) from error
                _write_build(existing.path, build)
                shutil.rmtree(folder, ignore_errors=True)
                return build
        try:
            if jar.name != JAR:
                jar.replace(folder / JAR)
            target = self._free(build_id(name, info.sha256, self._id_digits))
            build = self._build(target, info, name=name, prerelease=prerelease, source=source)
            _write_build(folder, build)
            folder.rename(target)  # the build appears whole, in one rename
        except OSError as error:
            raise _cannot("install into", self._root, error) from error  # noqa: TRY003
        return build

    def update(self, build: Build, *, prerelease: bool, source: Source) -> Build:
        """Rewrite ``build.json`` only: the jar and the id stay."""
        self._require_lock("updating a build")
        changed = replace(build, prerelease=prerelease, source=source)
        _write_build(build.path, changed)
        return changed

    def remove(self, build: Build) -> None:
        """``move_out``, then ``delete_out``: a reader never sees half a build."""
        out = self.move_out(build)
        if out is not None:
            self.delete_out(out)

    def pin(self, build: Build) -> None:
        self._require_lock("pinning a build")
        _write_atomic(self._pin, f"{build.id}\n")

    def unpin(self) -> None:
        self._require_lock("unpinning")
        try:
            self._pin.unlink(missing_ok=True)
        except OSError as error:
            raise _cannot("remove", self._pin, error) from error

    def move_out(self, build: Build) -> TmpFolder | None:
        """One rename takes the build into ``.tmp/``; None if it is no longer there."""
        self._require_lock("removing a build")
        current = _read_build(build.path)
        if current is None or current.name != build.name or current.sha256 != build.sha256:
            return None
        out = self.new_tmp()
        out.lock()
        try:
            build.path.rename(out.path)
        except FileNotFoundError:
            out.release()
            return None
        except OSError as error:
            out.release()
            raise _cannot("remove", build.path, error) from error
        return out

    def delete_out(self, out: TmpFolder) -> None:
        """Delete a folder ``move_out`` took out, then release it. What cannot be deleted is left to ``clean_tmp``."""
        self._require_lock("removing a build")
        out.discard()
        out.release()

    # ------------------------------------------------------------------ helpers

    def _free(self, first: str) -> Path:
        """The first id that does not exist: ``first``, then ``first-2``, ``first-3``, ..."""
        candidate, number = self._root / first, 1
        while candidate.exists() or candidate.is_symlink():
            number += 1
            candidate = self._root / f"{first}-{number}"
        return candidate

    def _build(self, folder: Path, info: JarInfo, *, name: str, prerelease: bool, source: Source) -> Build:
        return Build(
            id=folder.name,
            name=name,
            commit=info.commit,
            calver=info.calver,
            built_at=info.built_at,
            sha256=info.sha256,
            size=info.size,
            prerelease=prerelease,
            source=source,
            installed_at=self._now().astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            capabilities=info.capabilities,
            path=folder,
        )


def _stable(builds: list[Build]) -> list[Build]:
    """The builds of the highest-numbered name recorded as not prereleases (02 X4); empty if there are none."""
    released = [build for build in builds if not build.prerelease and version_key(build.name) is not None]
    if not released:
        return []
    best = min((build.name for build in released), key=name_key)
    return [build for build in released if build.name == best]
