"""A throwaway model of the tools store and its step-level mutations (design 12 V1, V3, V4, V11, V12).

It exists so that the state machine in ``test_tool_store.py`` can be run before
``tlaup.versioning.store`` and ``tlaup.versioning.install`` are written, to show that the
machine itself is sound. A "jar" here is a small file; nothing is downloaded or verified.
It is not product code: the work package that builds the store deletes this file and the
reference test with it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import filelock

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path


class StoreLocked(Exception):  # noqa: N818  (the design's name, 20 G2)
    pass


class PinnedBuildMissing(Exception):  # noqa: N818
    pass


@dataclass(frozen=True)
class Release:
    """What upstream publishes under a name now."""

    name: str
    version: int

    @property
    def content(self) -> bytes:
        return f"{self.name}:{self.version}".encode()

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True)
class JarInfo:
    sha256: str
    version: int


@dataclass(frozen=True)
class Build:
    id: str
    name: str
    sha256: str
    version: int
    path: Path

    @property
    def jar(self) -> Path:
        return self.path / "tla2tools.jar"


def fetch(release: Release, dest: Path) -> tuple[Path, JarInfo]:
    """Stands for fetch_build: put the published jar into ``dest``."""
    jar = dest / "tla2tools.jar"
    jar.write_bytes(release.content)
    return jar, JarInfo(release.sha256, release.version)


def _try(lock: filelock.FileLock, timeout: float) -> bool:
    try:
        if timeout > 0:
            lock.acquire(timeout=timeout)
        else:
            lock.acquire(blocking=False)
    except filelock.Timeout:
        return False
    return True


class TmpFolder:
    """A folder under .tmp/ with its lock file beside it (V11)."""

    def __init__(self, tmp: Path) -> None:
        name = uuid.uuid4().hex[:12]
        self.path = tmp / name
        self.lock_file = tmp / f"{name}.lock"
        self._lock = filelock.FileLock(self.lock_file)

    def lock(self) -> None:
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock.acquire(blocking=False)

    def make(self) -> None:
        self.path.mkdir()

    def discard(self) -> None:
        shutil.rmtree(self.path, ignore_errors=True)

    def release(self) -> None:
        self.lock_file.unlink(missing_ok=True)  # while the lock is held, as its last use
        self._lock.release()


class ToolStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.tmp = root / ".tmp"
        self.tmp.mkdir(parents=True, exist_ok=True)
        self._lock = filelock.FileLock(root / ".lock")

    # reads: no lock

    def builds(self) -> list[Build]:
        found = []
        for folder in self.root.iterdir():
            if folder.name.startswith(".") or not folder.is_dir():
                continue
            try:
                record = json.loads((folder / "build.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if (folder / "tla2tools.jar").is_file():
                found.append(Build(folder.name, record["name"], record["sha256"], record["version"], folder))
        return sorted(found, key=lambda build: (build.name, -build.version))

    def find(self, name: str) -> list[Build]:
        return [build for build in self.builds() if build.name == name]

    def pin_id(self) -> str | None:
        try:
            return (self.root / "pin").read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    def pinned(self) -> Build | None:
        pin = self.pin_id()
        if pin is None:
            return None
        for build in self.builds():
            if build.id == pin:
                return build
        raise PinnedBuildMissing(pin)

    # mutations: the caller holds the lock

    def acquire(self, timeout: float = 60.0) -> None:
        if not _try(self._lock, timeout):
            raise StoreLocked(str(self.root / ".lock"))

    def release(self) -> None:
        self._lock.release()

    def new_tmp(self) -> TmpFolder:
        return TmpFolder(self.tmp)

    def clean_tmp(self) -> None:
        for folder in [entry for entry in self.tmp.iterdir() if entry.is_dir()]:
            lock = filelock.FileLock(self.tmp / f"{folder.name}.lock")
            if _try(lock, 0):
                try:
                    shutil.rmtree(folder, ignore_errors=True)
                    (self.tmp / f"{folder.name}.lock").unlink(missing_ok=True)
                finally:
                    lock.release()

    def add(self, folder: Path, info: JarInfo, *, name: str) -> Build:
        for build in self.find(name):
            if build.sha256 == info.sha256:
                shutil.rmtree(folder, ignore_errors=True)
                return build
        record = {"schema": 1, "name": name, "sha256": info.sha256, "version": info.version}
        (folder / "build.json").write_text(json.dumps(record), encoding="utf-8")
        build_id = f"{name}-{info.sha256[:12]}"
        folder.rename(self.root / build_id)
        return Build(build_id, name, info.sha256, info.version, self.root / build_id)

    def move_out(self, build: Build) -> TmpFolder | None:
        """One rename takes the build out of the store; None if it is no longer there."""
        out = self.new_tmp()
        out.lock()
        try:
            build.path.rename(out.path)
        except OSError:
            out.release()
            return None
        return out

    def delete_out(self, out: TmpFolder) -> None:
        out.discard()
        out.release()

    def _write_pin(self, text: str) -> None:
        tmp = self.root / "pin.tmp"
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(self.root / "pin")

    def pin(self, build: Build) -> None:
        self._write_pin(build.id)

    def unpin(self) -> None:
        (self.root / "pin").unlink(missing_ok=True)


class _Mutation:
    def __init__(self, store: ToolStore) -> None:
        self.store = store

    def take_store_lock(self, timeout: float = 60.0) -> None:
        self.store.acquire(timeout)

    def clean_tmp(self) -> None:
        self.store.clean_tmp()

    def release_store_lock(self) -> None:
        self.store.release()


class _Download(_Mutation):
    """What install and upgrade share: the download outside the lock, and add under it."""

    def __init__(
        self,
        store: ToolStore,
        name: str,
        lookup: Callable[[str], Release],
        fetch: Callable[[Release, Path], tuple[Path, JarInfo]],
    ) -> None:
        super().__init__(store)
        self.name = name
        self.lookup = lookup
        self.fetch = fetch
        self.tmp: TmpFolder | None = None
        self.info: JarInfo | None = None
        self.build: Build | None = None

    def lock_tmp(self) -> None:
        self.tmp = self.store.new_tmp()
        self.tmp.lock()

    def make_tmp(self) -> None:
        assert self.tmp is not None
        self.tmp.make()

    def download(self) -> None:
        assert self.tmp is not None
        _, self.info = self.fetch(self.lookup(self.name), self.tmp.path)

    def give_up(self) -> None:
        if self.tmp is not None:
            self.tmp.discard()
            self.tmp.release()
            self.tmp = None

    def add(self) -> bool:
        """False: nothing was downloaded and the build that was found has gone; start again."""
        if self.tmp is not None and self.info is not None:
            self.build = self.store.add(self.tmp.path, self.info, name=self.name)
            return True
        found = self.build  # read under the lock
        return found is not None and any(build.id == found.id for build in self.store.builds())

    def release_tmp(self) -> None:
        if self.tmp is not None:
            self.tmp.release()
            self.tmp = None


class Install(_Download):
    def look(self) -> bool:
        """True if what upstream publishes has to be downloaded."""
        release = self.lookup(self.name)
        for build in self.store.find(self.name):
            if build.sha256 == release.sha256:
                self.build = build
                return False
        return True

    def pin_if_none(self) -> None:
        if self.build is not None and self.store.pin_id() is None:  # read under the lock
            self.store.pin(self.build)


class Upgrade(_Download):
    old: Build | None = None
    _out: TmpFolder | None = None

    def look(self) -> bool:
        installed = self.store.find(self.name)
        self.old = installed[0] if installed else None
        return self.old is None or self.old.sha256 != self.lookup(self.name).sha256

    def move_pin(self) -> None:
        if self.build is not None and self.old is not None and self.store.pin_id() == self.old.id:
            self.store.pin(self.build)

    def move_old_out(self) -> None:
        if self.old is not None and self.build is not None and self.old.id != self.build.id:
            self._out = self.store.move_out(self.old)

    def delete_old(self) -> None:
        if self._out is not None:
            self.store.delete_out(self._out)
            self._out = None


class Uninstall(_Mutation):
    def __init__(self, store: ToolStore, builds: Sequence[Build]) -> None:
        super().__init__(store)
        self.builds = list(builds)
        self.removed: list[Build] = []
        self._out: list[TmpFolder] = []

    def move_out(self) -> None:
        for build in self.builds:
            out = self.store.move_out(build)
            if out is not None:
                self.removed.append(build)
                self._out.append(out)

    def delete_out(self) -> None:
        for out in self._out:
            self.store.delete_out(out)
        self._out = []

    def clear_pin(self) -> None:
        if self.store.pin_id() in {build.id for build in self.removed}:  # read under the lock
            self.store.unpin()


class Pin(_Mutation):
    def __init__(self, store: ToolStore, build: Build) -> None:
        super().__init__(store)
        self.build = build

    def write_pin(self) -> bool:
        """False if the build is no longer installed (VersionNotFound in the command)."""
        if all(build.id != self.build.id for build in self.store.builds()):
            return False
        self.store.pin(self.build)
        return True
