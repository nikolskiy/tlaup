"""Stateful property test of the tools store (design 12 V1, V3, V4, V11, V12): the mirror of specs/ToolStore.tla.

Each tlaup process of the spec is a ``Proc`` holding its own step object (an install, an
upgrade, an uninstall or a pin in progress, with its own locks) and its position. Each
action of the spec is a rule with the action's enabling condition as its precondition.
The safety properties are checked on the real files after every step.

What differs from the spec, and why:

- A reader's "read the pin" and "look the build up" are one call, ``ToolStore.pinned()``.
- Upstream is a table of the test's own: a name and the version of its bytes now.
- A killed tlaup is a ``Proc`` whose step object is dropped, which releases its locks as
  the operating system would and leaves its folders under ``.tmp/``.

The machine runs against ``tlaup.versioning``: the store of ``store.py`` and the steps of
``install.py``.
"""

from __future__ import annotations

import gc
import hashlib
import importlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("hypothesis")
pytest.importorskip("filelock")

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)

PROJECT_ROOT = Path(__file__).parents[2]
PROCESSES = 2  # as in the spec's model; a third process makes two commands seldom meet
NAMES = ["rolling", "v1.8.0"]
MAX_VERSION = 3
MAX_KILLS = 1  # as in the spec's model; more would seldom let a command get anywhere
MAX_GIVE_UPS = 1  # failed downloads and lock timeouts in one example, for the same reason
ANY = object()  # the pin may become anything (`tool pin`)
# The store's clock. Builds with no build time are ordered by install time, so the real clock's seconds
# would make the order, and with it what the rules draw, differ between runs of one example.
FIXED_NOW = datetime(2026, 11, 18, 10, 0, 0, tzinfo=UTC)


def tlaup_impl() -> SimpleNamespace:
    errors = importlib.import_module("tlaup.errors")
    paths = importlib.import_module("tlaup.paths")
    store = importlib.import_module("tlaup.versioning.store")
    remote = importlib.import_module("tlaup.versioning.remote")
    jarinfo = importlib.import_module("tlaup.versioning.jarinfo")

    def jar_bytes(name: str, version: int, dest: Path) -> Path:
        """A small real jar: what read_jar asks for, and bytes that differ by version."""
        jar = dest / "tla2tools.jar"
        with zipfile.ZipFile(jar, "w") as archive:
            manifest = f"Manifest-Version: 1.0\nX-Git-Revision: {version:040x}\n"
            archive.writestr(zipfile.ZipInfo("META-INF/MANIFEST.MF", date_time=(2026, 11, 18, 10, 0, 0)), manifest)
            archive.writestr(zipfile.ZipInfo("tlc2/TLC.class", date_time=(2026, 11, 18, 10, 0, 0)), f"{name}:{version}")
        return jar

    def release(name: str, version: int) -> Any:
        with tempfile.TemporaryDirectory() as scratch:
            content = jar_bytes(name, version, Path(scratch)).read_bytes()
        asset = remote.Asset(
            id=version,
            size=len(content),
            digest="sha256:" + hashlib.sha256(content).hexdigest(),
            updated_at="2026-11-18T10:00:00Z",
            download_url=f"https://example.invalid/{name}/{version}/tla2tools.jar",
        )
        return remote.Release(
            tag=name, prerelease=False, draft=False, created_at=asset.updated_at, published_at=None, asset=asset
        )

    def fetch(published: Any, dest: Path) -> tuple[Path, Any]:
        jar = jar_bytes(published.tag, published.asset.id, dest)
        return jar, jarinfo.read_jar(jar)

    def app_paths(root: Path) -> Any:
        return paths.AppPaths.from_env({"TLAUP_HOME": str(root)})

    return SimpleNamespace(
        name=store.__name__,
        steps=importlib.import_module("tlaup.versioning.install"),
        make_store=lambda root: store.ToolStore(app_paths(root), now=lambda: FIXED_NOW),
        tool_dir=lambda root: app_paths(root).tools,
        release=release,
        fetch=fetch,
        locked=(errors.StoreLocked,),
        missing=(errors.PinnedBuildMissing,),
    )


@dataclass
class Proc:
    """One tlaup process: its command in progress (and so its locks) and where it is."""

    name: str
    pc: str = "idle"
    cmd: str = ""
    op: Any = None
    tmp: Path | None = None  # its download folder under .tmp/, while it must exist
    read: Any = None

    def forget(self) -> None:
        self.pc, self.cmd, self.op, self.tmp, self.read = "idle", "", None, None, None


class ToolStoreMachine(RuleBasedStateMachine):
    impl: SimpleNamespace
    base: Path

    def __init__(self) -> None:
        super().__init__()
        self.root = Path(tempfile.mkdtemp(dir=self.base))
        self.tool = self.impl.tool_dir(self.root)
        self.tool.mkdir(parents=True, exist_ok=True)
        self.store = self.impl.make_store(self.root)  # the readers' view; mutations make their own
        self.procs = [Proc(f"p{i}") for i in range(PROCESSES)]
        self.published = dict.fromkeys(NAMES, 1)
        self.holder: Proc | None = None  # who holds the store lock
        self.killed_removed: set[str] = set()  # FC4: what a killed uninstall had removed
        self.pin_at_kill: str | None = None  # ...and the pin then, until the pin is next written
        self.kills = 0
        self.give_ups = 0
        self.pin_before = self.pin_on_disk()
        self.pin_allowed: set[Any] = set()

    def teardown(self) -> None:
        for proc in self.procs:
            proc.forget()
        self.store = None
        gc.collect()
        shutil.rmtree(self.root, ignore_errors=True)

    # ------------------------------------------------------------------ helpers

    def at(self, *pcs: str) -> list[Proc]:
        return [proc for proc in self.procs if proc.pc in pcs]

    def lookup(self, name: str) -> Any:
        return self.impl.release(name, self.published[name])

    def pin_on_disk(self) -> str | None:
        try:
            return (self.tool / "pin").read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    def folders(self) -> list[Path]:
        return sorted(entry for entry in self.tool.iterdir() if entry.is_dir() and not entry.name.startswith("."))

    def new_store(self) -> Any:
        """Each process has its own store object, and so its own lock object."""
        return self.impl.make_store(self.root)

    def draw_at(self, data: st.DataObject, *pcs: str, cmd: tuple[str, ...] = ()) -> Proc:
        procs = [proc for proc in self.at(*pcs) if not cmd or proc.cmd in cmd]
        return data.draw(st.sampled_from(procs), label="process")

    def any_at(self, *pcs: str, cmd: tuple[str, ...] = ()) -> bool:
        return any(not cmd or proc.cmd in cmd for proc in self.at(*pcs))

    # ------------------------------------------------------------------ earlier commands

    @initialize(data=st.data())
    def earlier_commands(self, data: st.DataObject) -> None:
        """Leave behind what earlier commands left, made with the same steps.

        Random steps alone seldom get as far as two builds and a pin before two commands
        race; with this the interleaving starts from a store that already holds something.
        """
        for _ in range(data.draw(st.integers(0, 3), label="earlier commands")):
            name = data.draw(st.sampled_from(NAMES), label="name")
            if data.draw(st.booleans(), label="upstream publishes first"):
                self.published[name] = min(self.published[name] + 1, MAX_VERSION)
            install = self.impl.steps.Install(self.new_store(), name, self.lookup, self.impl.fetch)
            download = install.look()
            if download:
                install.lock_tmp()
                install.make_tmp()
                install.download()
            install.take_store_lock(timeout=0)
            assert install.add()
            install.pin_if_none()
            install.release_store_lock()
            if download:
                install.release_tmp()
        if data.draw(st.booleans(), label="upstream publishes afterwards"):
            name = data.draw(st.sampled_from(NAMES), label="name")
            self.published[name] = min(self.published[name] + 1, MAX_VERSION)
        self.pin_before = self.pin_on_disk()

    # ------------------------------------------------------------------ commands start without the lock

    @precondition(lambda self: self.at("idle"))
    @rule(data=st.data(), name=st.sampled_from(NAMES))
    def start_install(self, data: st.DataObject, name: str) -> None:
        proc = self.draw_at(data, "idle")
        proc.cmd = "install"
        proc.op = self.impl.steps.Install(self.new_store(), name, self.lookup, self.impl.fetch)
        proc.pc = "tLock" if proc.op.look() else "sLock"

    @precondition(lambda self: self.at("idle") and self.store.builds())
    @rule(data=st.data())
    def start_upgrade(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "idle")
        name = data.draw(st.sampled_from(sorted({build.name for build in self.store.builds()})), label="name")
        op = self.impl.steps.Upgrade(self.new_store(), name, self.lookup, self.impl.fetch)
        if op.look():  # otherwise it is up to date and the command ends
            proc.cmd, proc.op, proc.pc = "upgrade", op, "tLock"

    @precondition(lambda self: self.at("idle") and self.store.builds())
    @rule(data=st.data(), cmd=st.sampled_from(["uninstall", "pin"]))
    def start_uninstall_or_pin(self, data: st.DataObject, cmd: str) -> None:
        proc = self.draw_at(data, "idle")
        build = data.draw(st.sampled_from(self.store.builds()), label="build")
        proc.cmd = cmd
        if cmd == "uninstall":
            proc.op = self.impl.steps.Uninstall(self.new_store(), [build])
        else:
            proc.op = self.impl.steps.Pin(self.new_store(), build)
        proc.pc = "sLock"

    # ------------------------------------------------------------------ the download, outside the lock

    @precondition(lambda self: self.at("tLock"))
    @rule(data=st.data())
    def lock_tmp(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "tLock")
        proc.op.lock_tmp()
        proc.pc = "tMkdir"

    @precondition(lambda self: self.at("tMkdir"))
    @rule(data=st.data())
    def make_tmp(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "tMkdir")
        proc.op.make_tmp()
        proc.tmp = proc.op.tmp.path
        proc.pc = "dl"

    @precondition(lambda self: self.at("dl"))
    @rule(data=st.data())
    def download(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "dl")
        proc.op.download()
        proc.pc = "sLock"

    def may_give_up(self) -> list[Proc]:
        waiting = [proc for proc in self.at("sLock") if self.holder is not None]
        return self.at("dl") + waiting

    @precondition(lambda self: self.may_give_up() and self.give_ups < MAX_GIVE_UPS)
    @rule(data=st.data())
    def give_up(self, data: st.DataObject) -> None:
        """A failed download, or StoreLocked after the wait."""
        proc = data.draw(st.sampled_from(self.may_give_up()), label="process")
        self.give_ups += 1
        if proc.cmd in {"install", "upgrade"}:
            proc.tmp = None
            proc.op.give_up()
        proc.forget()

    # ------------------------------------------------------------------ under the store lock

    @precondition(lambda self: self.at("sLock"))
    @rule(data=st.data())
    def take_store_lock(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "sLock")
        try:
            proc.op.take_store_lock(timeout=0)
        except self.impl.locked:
            assert self.holder is not None, "the store lock was free and could not be taken"
            return
        assert self.holder is None, f"two processes hold the store lock: {self.holder.name} and {proc.name}"
        self.holder = proc
        proc.pc = "locked"

    @precondition(lambda self: self.at("locked"))
    @rule(data=st.data())
    def clean_tmp(self, data: st.DataObject) -> None:
        self.draw_at(data, "locked").op.clean_tmp()

    @precondition(lambda self: self.any_at("locked", cmd=("install", "upgrade")))
    @rule(data=st.data())
    def add(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "locked", cmd=("install", "upgrade"))
        proc.tmp = None  # moved into place or discarded from here on
        if proc.op.add():
            proc.pc = "added"
            return
        # The build an install found installed has gone: it starts again (finding K2-5).
        assert proc.cmd == "install", "only an install that downloaded nothing can have nothing to add"
        proc.op.release_store_lock()
        self.holder = None
        assert proc.op.look(), "the build is gone, so there is something to download"
        proc.pc = "tLock"

    @precondition(lambda self: self.at("added"))
    @rule(data=st.data())
    def pin_step(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "added")
        pin = self.pin_on_disk()
        if proc.cmd == "install":
            if pin is None or not (self.tool / pin / "build.json").is_file():  # nothing pinned (V12, FC5)
                self.pin_allowed = {proc.op.build.id}
            proc.op.pin_if_none()
            pinned = self.pin_on_disk()
            if pinned != pin:
                gone = "InstallPinsInstalled: pinned a build that is gone"
                assert (self.tool / pinned / "tla2tools.jar").is_file(), gone
            proc.pc = "sUnlock"
        else:
            if proc.op.old is not None and pin == proc.op.old.id:
                self.pin_allowed = {proc.op.build.id}
            proc.op.move_pin()
            proc.pc = "rm"

    @precondition(lambda self: self.at("rm") or self.any_at("locked", cmd=("uninstall",)))
    @rule(data=st.data())
    def move_out(self, data: st.DataObject) -> None:
        procs = self.at("rm") + [proc for proc in self.at("locked") if proc.cmd == "uninstall"]
        proc = data.draw(st.sampled_from(procs), label="process")
        if proc.cmd == "upgrade":
            proc.op.move_old_out()
        else:
            proc.op.move_out()
        proc.pc = "rmDel"

    @precondition(lambda self: self.at("rmDel"))
    @rule(data=st.data())
    def delete_out(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "rmDel")
        if proc.cmd == "upgrade":
            proc.op.delete_old()
            proc.pc = "sUnlock"
        else:
            proc.op.delete_out()
            proc.pc = "unpin"

    @precondition(lambda self: self.at("unpin"))
    @rule(data=st.data())
    def clear_pin(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "unpin")
        if self.pin_on_disk() in {build.id for build in proc.op.removed}:
            self.pin_allowed = {None}
        proc.op.clear_pin()
        proc.pc = "sUnlock"

    @precondition(lambda self: self.any_at("locked", cmd=("pin",)))
    @rule(data=st.data())
    def write_pin(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "locked", cmd=("pin",))
        self.pin_allowed = {ANY}
        proc.op.write_pin()
        pin = self.pin_on_disk()
        if pin != self.pin_before:
            assert (self.tool / pin / "tla2tools.jar").is_file(), "PinWritesInstalled: pinned a build that is gone"
        proc.pc = "sUnlock"

    @precondition(lambda self: self.at("sUnlock"))
    @rule(data=st.data())
    def release_store_lock(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "sUnlock")
        proc.op.release_store_lock()
        self.holder = None
        if proc.cmd in {"install", "upgrade"}:
            proc.pc = "tUnlock"
        else:
            proc.forget()

    @precondition(lambda self: self.at("tUnlock"))
    @rule(data=st.data())
    def release_tmp(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "tUnlock")
        proc.op.release_tmp()
        proc.forget()

    # ------------------------------------------------------------------ a reader, with no lock

    @precondition(lambda self: self.at("idle"))
    @rule(data=st.data())
    def reader_pinned(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "idle")
        pin = self.pin_on_disk()
        try:
            build = self.store.pinned()
        except self.impl.missing:
            assert pin is not None, "PinnedBuildMissing with nothing pinned"
            return
        if build is None:
            assert pin is None, "pinned() gave nothing while a build is pinned"
            return
        assert build.id == pin, "ReaderOutcome: pinned() gave another build than the pin names"
        proc.cmd, proc.read, proc.pc = "read", build, "rOpen"

    @precondition(lambda self: self.at("rOpen"))
    @rule(data=st.data())
    def reader_opens_the_jar(self, data: st.DataObject) -> None:
        proc = self.draw_at(data, "rOpen")
        try:
            content = proc.read.jar.read_bytes()
        except OSError:
            content = None  # removed since the check: Java's own error, finding K2-3
        if content is not None:
            digest = hashlib.sha256(content).hexdigest()
            assert digest == proc.read.sha256, "ReaderOutcome: the jar is not the build the pin named"
        proc.forget()

    # ------------------------------------------------------------------ the environment

    @precondition(lambda self: self.kills < MAX_KILLS and any(proc.pc != "idle" for proc in self.procs))
    @rule(data=st.data())
    def kill(self, data: st.DataObject) -> None:
        proc = data.draw(st.sampled_from([p for p in self.procs if p.pc != "idle"]), label="process")
        self.kills += 1
        if self.holder is proc:
            self.holder = None
            if proc.cmd == "uninstall" and proc.op is not None:
                self.killed_removed = {build.id for build in proc.op.removed}
                self.pin_at_kill = self.pin_on_disk()
        proc.forget()
        gc.collect()

    @rule(name=st.sampled_from(NAMES))
    def upstream_publishes(self, name: str) -> None:
        if self.published[name] < MAX_VERSION:
            self.published[name] += 1

    # ------------------------------------------------------------------ the properties, on the files

    @invariant()
    def pin_is_consistent(self) -> None:
        pin = self.pin_on_disk()
        if pin != self.pin_at_kill:  # the pin was written since the kill: the exception is over
            self.killed_removed, self.pin_at_kill = set(), None
        accepted = pin in self.killed_removed  # the state D50 accepts, and only that one (FC4)
        if self.holder is None and not accepted and pin is not None:
            assert (self.tool / pin / "build.json").is_file(), f"PinConsistent: the pin names {pin}, which is gone"

    @invariant()
    def pin_never_moves_silently(self) -> None:
        pin = self.pin_on_disk()
        if pin != self.pin_before:
            allowed = ANY in self.pin_allowed or pin in self.pin_allowed
            assert allowed, f"PinNeverMovesSilently: the pin went from {self.pin_before} to {pin}"
        self.pin_before = pin
        self.pin_allowed = set()

    @invariant()
    def no_partial_build_and_no_duplicate(self) -> None:
        seen: set[tuple[str, str]] = set()
        for folder in self.folders():
            jar, record = folder / "tla2tools.jar", folder / "build.json"
            assert jar.is_file(), f"NoPartialBuild: {folder.name} has no jar"
            assert record.is_file(), f"NoPartialBuild: {folder.name} has no build.json"
            build = json.loads(record.read_text(encoding="utf-8"))
            digest = hashlib.sha256(jar.read_bytes()).hexdigest()
            assert digest == build["sha256"], f"NoPartialBuild: the jar of {folder.name} is not the recorded one"
            key = (build["name"], build["sha256"])
            assert key not in seen, f"NoDuplicate: two builds are {key}"
            seen.add(key)

    @invariant()
    def a_live_owner_keeps_its_tmp_folder(self) -> None:
        for proc in self.procs:
            if proc.tmp is not None:
                assert proc.tmp.is_dir(), f"TmpOwnerSafe: the download folder of {proc.name} was removed"


def run_machine(impl: SimpleNamespace, base: Path) -> None:
    machine = type("ToolStore", (ToolStoreMachine,), {"impl": impl, "base": base})
    run_state_machine_as_test(machine, settings=settings(stateful_step_count=80))


def test_tool_store_machine(tmp_path: Path) -> None:
    run_machine(tlaup_impl(), tmp_path)


# The counterexamples of findings K2-1 and K2-5 (specs/README.md), replayed step by step, and
# the repair of finding FC5 of the 2026-11-20 review.
# The machine above finds races like these by chance; these tests find them always.


class Scripted:
    """Two tlaup processes whose steps a test calls in a fixed order."""

    def __init__(self, impl: SimpleNamespace, root: Path) -> None:
        self.impl = impl
        self.root = root
        self.tool = impl.tool_dir(root)
        self.tool.mkdir(parents=True, exist_ok=True)

    def lookup(self, name: str) -> Any:
        return self.impl.release(name, 1)

    def pin(self) -> str | None:
        try:
            return (self.tool / "pin").read_text(encoding="utf-8").strip() or None
        except OSError:
            return None

    def install(self, name: str) -> Any:
        """An install that has downloaded and waits for the store lock."""
        op = self.impl.steps.Install(self.impl.make_store(self.root), name, self.lookup, self.impl.fetch)
        assert op.look()
        op.lock_tmp()
        op.make_tmp()
        op.download()
        return op

    def finish(self, op: Any) -> None:
        op.take_store_lock(timeout=0)
        assert op.add()
        op.pin_if_none()
        op.release_store_lock()
        op.release_tmp()

    def build(self, name: str) -> Any:
        (found,) = [build for build in self.impl.make_store(self.root).builds() if build.name == name]
        return found


def second_install_leaves_the_pin(impl: SimpleNamespace, root: Path) -> None:
    """variants/ToolStore-stale-pin-moves.cfg: both installs start with nothing pinned."""
    world = Scripted(impl, root)
    first, second = world.install("rolling"), world.install("v1.8.0")
    world.finish(first)
    pinned = world.pin()
    assert pinned == first.build.id
    world.finish(second)
    assert world.pin() == pinned, "PinNeverMovesSilently: the second install replaced the pin"


def uninstall_clears_a_pin_written_after_it_started(impl: SimpleNamespace, root: Path) -> None:
    """variants/ToolStore-stale-pin-dangles.cfg: the build is pinned after the uninstall found it."""
    world = Scripted(impl, root)
    install = world.install("rolling")
    install.take_store_lock(timeout=0)
    assert install.add()
    uninstall = impl.steps.Uninstall(impl.make_store(root), [world.build("rolling")])  # nothing is pinned yet
    install.pin_if_none()
    install.release_store_lock()
    install.release_tmp()
    assert world.pin() == install.build.id
    uninstall.take_store_lock(timeout=0)
    uninstall.move_out()
    uninstall.delete_out()
    uninstall.clear_pin()
    uninstall.release_store_lock()
    assert world.pin() is None, "PinConsistent: the pin names the build that was removed"


def pin_refuses_a_build_removed_after_it_was_found(impl: SimpleNamespace, root: Path) -> None:
    """variants/ToolStore-stale-pin-missing.cfg: the build goes between `pin` finding it and writing it."""
    world = Scripted(impl, root)
    world.finish(world.install("rolling"))
    world.finish(world.install("v1.8.0"))
    pinned = world.pin()
    pin = impl.steps.Pin(impl.make_store(root), world.build("v1.8.0"))
    uninstall = impl.steps.Uninstall(impl.make_store(root), [world.build("v1.8.0")])
    uninstall.take_store_lock(timeout=0)
    uninstall.move_out()
    uninstall.delete_out()
    uninstall.clear_pin()
    uninstall.release_store_lock()
    pin.take_store_lock(timeout=0)
    written = pin.write_pin()
    pin.release_store_lock()
    assert not written, "PinWritesInstalled: `pin` wrote a build that had been removed"
    assert world.pin() == pinned


def install_starts_again_when_the_build_it_found_has_gone(impl: SimpleNamespace, root: Path) -> None:
    """variants/ToolStore-stale-install-found.cfg, finding K2-5: found installed, then removed."""
    world = Scripted(impl, root)
    world.finish(world.install("rolling"))
    again = impl.steps.Install(impl.make_store(root), "rolling", world.lookup, impl.fetch)
    assert not again.look(), "what upstream publishes is installed: nothing to download"
    uninstall = impl.steps.Uninstall(impl.make_store(root), [world.build("rolling")])
    uninstall.take_store_lock(timeout=0)
    uninstall.move_out()
    uninstall.delete_out()
    uninstall.clear_pin()
    uninstall.release_store_lock()
    assert world.pin() is None
    again.take_store_lock(timeout=0)
    assert not again.add(), "the build that was found is gone: there is nothing to pin"
    again.release_store_lock()
    assert world.pin() is None, "InstallPinsInstalled: the install pinned a build that had been removed"
    assert again.look(), "starting again, there is something to download"
    again.lock_tmp()
    again.make_tmp()
    again.download()
    world.finish(again)
    assert world.pin() == world.build("rolling").id


def install_repairs_the_pin_a_killed_uninstall_left(impl: SimpleNamespace, root: Path) -> None:
    """Finding FC5 of the 2026-11-20 review: after the state D50 accepts, an install puts it right (V3)."""
    world = Scripted(impl, root)
    world.finish(world.install("rolling"))
    pinned = world.pin()
    uninstall = impl.steps.Uninstall(impl.make_store(root), [world.build("rolling")])
    uninstall.take_store_lock(timeout=0)
    uninstall.move_out()
    uninstall.delete_out()
    uninstall.release_store_lock()  # killed before it cleared the pin: the system frees the lock
    assert world.pin() == pinned, "the kill left the pin naming the removed build (D50)"
    world.finish(world.install("rolling"))
    assert world.pin() == world.build("rolling").id, "an install left a pin that names a missing build"


TRACES = [
    install_repairs_the_pin_a_killed_uninstall_left,
    second_install_leaves_the_pin,
    uninstall_clears_a_pin_written_after_it_started,
    pin_refuses_a_build_removed_after_it_was_found,
    install_starts_again_when_the_build_it_found_has_gone,
]


@pytest.mark.parametrize("trace", TRACES)
def test_counterexample(trace: Any, tmp_path: Path) -> None:
    trace(tlaup_impl(), tmp_path)


# One lock object in this process must stand for another tlaup process: the machine above
# rests on it. A second Python process confirms it for the store lock.

CHILD = """
import importlib, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
test = importlib.import_module("tests.stateful.test_tool_store")
impl = getattr(test, sys.argv[2])()
store = impl.make_store(Path(sys.argv[3]))
try:
    store.acquire(timeout=0)
except impl.locked:
    print("refused", flush=True)
else:
    print("held", flush=True)
    sys.stdin.readline()
"""


def child(impl_name: str, root: Path) -> subprocess.Popen[str]:
    argv = [sys.executable, "-c", CHILD, str(PROJECT_ROOT), impl_name, str(root)]
    return subprocess.Popen(argv, cwd=PROJECT_ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)


def second_process_agrees(impl: SimpleNamespace, impl_name: str, root: Path) -> None:
    impl.tool_dir(root).mkdir(parents=True, exist_ok=True)
    first, second = impl.make_store(root), impl.make_store(root)

    first.acquire(timeout=0)
    with pytest.raises(impl.locked):
        second.acquire(timeout=0)
    other = child(impl_name, root)
    assert other.communicate(timeout=30)[0].strip() == "refused", "another process got the held store lock"
    first.release()

    other = child(impl_name, root)
    try:
        assert other.stdout is not None
        assert other.stdout.readline().strip() == "held", "another process could not take the free store lock"
        with pytest.raises(impl.locked):
            second.acquire(timeout=0)
    finally:
        other.communicate("\n", timeout=30)
    second.acquire(timeout=0)
    second.release()


def test_a_store_object_stands_for_a_process(tmp_path: Path) -> None:
    second_process_agrees(tlaup_impl(), "tlaup_impl", tmp_path)
