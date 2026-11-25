"""Install, upgrade, uninstall and pin as steps, and the functions that run them (design 12 V1, V3, V4, V11, V12).

Each command is a class whose methods are the actions of ``specs/ToolStore.tla``, one call each, and a
function that calls them in order. The stateful test calls the steps one at a time from several objects,
each with its own store object and so its own locks, so a step object keeps no lock alive past itself.

The rule a step must keep: what a mutation decides on is read under the store lock (V1, findings K2-1
and K2-5). What is read before ``take_store_lock`` decides only whether to download.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from tlaup.errors import (
    AmbiguousVersion,
    FileOperationError,
    InternalError,
    NetworkError,
    NoPinnedBuild,
    NoToolsInstalled,
    PinnedBuildMissing,
    RateLimited,
    RemoteDataError,
    UsageError,
    VersionNotFound,
)
from tlaup.versioning.download import fetch_build, usable_digest
from tlaup.versioning.jarinfo import JarInfo
from tlaup.versioning.order import version_key
from tlaup.versioning.remote import Release
from tlaup.versioning.spec import VersionSpec, format_build
from tlaup.versioning.store import STABLE, Source

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tlaup.errors import TlaupError
    from tlaup.ui import Ui
    from tlaup.versioning.github import GitHubClient, Progress
    from tlaup.versioning.remote import Remote
    from tlaup.versioning.store import Build, TmpFolder, ToolStore

Lookup = Callable[[str], Release]  # what upstream publishes under a name now (V8)
Fetch = Callable[[Release, Path], tuple[Path, JarInfo]]  # fetch_build with the client bound (V5)


class _Identity(Protocol):
    """What a build spec is checked against: a verified jar (``JarInfo``) or an installed ``Build``."""

    @property
    def commit(self) -> str | None: ...
    @property
    def calver(self) -> str | None: ...
    @property
    def sha256(self) -> str: ...


LOCK_TIMEOUT = 60.0  # seconds (V11)
_CANNOT_ASK = (NetworkError, RateLimited, RemoteDataError)  # "GitHub cannot be asked" (V12)


def _out_of_order(what: str) -> InternalError:
    return InternalError(f"the install steps were called out of order: {what}")


def same_as_published(build: Build, release: Release) -> bool:
    """Whether ``build`` is what upstream publishes in ``release`` (V12, shared with upgrade, V4).

    By the release's ``sha256:`` digest where it has one; otherwise by the asset's size and upload time.
    A release with no jar is never the same.
    """
    asset = release.asset
    if asset is None:
        return False
    digest = usable_digest(asset)
    if digest is not None:
        return digest == build.sha256
    return asset.size == build.size and asset.updated_at == build.source.asset_updated_at


def _source(release: Release) -> Source:
    """The source record of a download of ``release``'s jar."""
    asset = release.asset
    if asset is None:  # fetch_build refuses a release with no jar before this is reached
        message = f"the release {release.tag!r} has no jar"
        raise VersionNotFound(message)
    return Source(
        kind="github-release",
        url=asset.download_url,
        asset_id=asset.id,
        asset_updated_at=asset.updated_at,
        digest_checked=usable_digest(asset) is not None,
    )


def _installed(store: ToolStore, build: Build) -> Build | None:
    """The build as the store holds it now: the same id, name and bytes; None if it has gone."""
    for current in store.builds():
        if (current.id, current.name, current.sha256) == (build.id, build.name, build.sha256):
            return current
    return None


def _pinned(store: ToolStore) -> Build | None:
    """The pinned build; None when nothing is pinned, which includes a pin naming a missing build (FC5)."""
    try:
        return store.pinned()
    except PinnedBuildMissing:
        return None


# ---------------------------------------------------------------------- the steps


class _Locked:
    """The store lock and the ``.tmp/`` cleanup, which every command takes the same way."""

    def __init__(self, store: ToolStore) -> None:
        self.store = store
        self._holding = False

    def take_store_lock(self, timeout: float = LOCK_TIMEOUT) -> None:
        """Wait at most ``timeout`` seconds; 0 is one attempt. ``StoreLocked`` after that."""
        self.store.acquire(timeout)
        self._holding = True

    def clean_tmp(self) -> None:
        self.store.clean_tmp()

    def release_store_lock(self) -> None:
        if self._holding:
            self._holding = False
            self.store.release()


class _Download(_Locked):
    """What install and upgrade share: the download outside the lock, and ``add`` under it."""

    def __init__(self, store: ToolStore, name: str, lookup: Lookup, fetch: Fetch) -> None:
        super().__init__(store)
        self.name = name
        self.lookup = lookup
        self.fetch = fetch
        self.tmp: TmpFolder | None = None
        self.build: Build | None = None
        self.release: Release | None = None  # what look() looked up
        self.info: JarInfo | None = None  # what download() verified
        self.downloaded = False  # a download was made, in this attempt or an earlier one
        self.already_installed = False  # the store held this name and these bytes
        self._jar: Path | None = None
        self._repair = False

    def _installed_of_name(self) -> list[Build]:
        return [build for build in self.store.builds() if build.name == self.name]  # newest first (V2)

    def lock_tmp(self) -> None:
        self.tmp = self.store.new_tmp()
        self.tmp.lock()

    def make_tmp(self) -> None:
        if self.tmp is None:
            what = "make_tmp before lock_tmp"
            raise _out_of_order(what)
        self.tmp.make()

    def download(self) -> None:
        """Fetch the release ``look()`` found into the temporary folder and verify it."""
        if self.tmp is None or self.release is None:
            what = "download before look and make_tmp"
            raise _out_of_order(what)
        self._jar, self.info = self.fetch(self.release, self.tmp.path)
        self.downloaded = True

    def give_up(self) -> None:
        """A failed download, or StoreLocked: discard the temporary folder and release its lock."""
        if self.tmp is not None:
            self.tmp.discard()
            self.tmp.release()
            self.tmp = None
        self._jar = None
        self.info = None

    def add(self) -> bool:
        """Under the lock: add the download, or check that the build ``look()`` found is still there.

        False: nothing was downloaded and that build has gone; the command starts again at ``look()``.
        """
        if self._jar is not None and self.info is not None and self.release is not None:
            self._add_download(self._jar, self.info, self.release)
            self._jar = None
            return True
        found = self.build
        current = None if found is None else _installed(self.store, found)
        if current is None:
            self.build = None
            return False
        self.build = current if self.release is None else self._refresh(current, self.release)
        self.already_installed = True
        return True

    def _add_download(self, jar: Path, info: JarInfo, release: Release) -> None:
        source = _source(release)
        before = {(build.name, build.sha256) for build in self.store.builds()}
        build = self.store.add(
            jar, info, name=self.name, prerelease=release.prerelease, source=source, repair=self._repair
        )
        self.already_installed = (build.name, build.sha256) in before
        if build.prerelease != release.prerelease or build.source != source:
            build = self.store.update(build, prerelease=release.prerelease, source=source)  # V12, row 4
        self.build = build

    def _refresh(self, build: Build, release: Release) -> Build:
        """Write upstream's ``prerelease`` flag and source record when they changed (V12, row 2)."""
        if release.asset is None:
            return build
        source = _source(release)
        # Not downloaded now: the record was compared with a digest then, or the digest equals the jar's now.
        source = Source(
            source.kind, source.url, source.asset_id, source.asset_updated_at,
            build.source.digest_checked or source.digest_checked,
        )  # fmt: skip
        if build.prerelease == release.prerelease and build.source == source:
            return build
        return self.store.update(build, prerelease=release.prerelease, source=source)

    def release_tmp(self) -> None:
        if self.tmp is not None:
            self.tmp.release()
            self.tmp = None


class Install(_Download):
    """``install()``'s steps: look, lock_tmp, make_tmp, download, take_store_lock, clean_tmp, add,
    pin_if_none, release_store_lock, release_tmp."""

    def __init__(self, store: ToolStore, name: str, lookup: Lookup, fetch: Fetch, *, force: bool = False) -> None:
        super().__init__(store, name, lookup, fetch)
        self.force = force
        self._repair = force
        self.pinned = False  # this command pinned its build

    def look(self) -> bool:
        """True: there is something to download. Without ``force``, the newest build of the name that is
        what upstream publishes is "already there"."""
        self.release = self.lookup(self.name)
        self.build = None
        if not self.force:
            for build in self._installed_of_name():
                if same_as_published(build, self.release):
                    self.build = build
                    return False
        return True

    def pin_if_none(self) -> None:
        """Pin the build when nothing is pinned, read now, under the lock (V12, "The pin")."""
        if self.build is not None and _pinned(self.store) is None:
            self.store.pin(self.build)
            self.pinned = True


class Upgrade(_Download):
    """As ``Install``, with move_pin, move_old_out and delete_old in place of pin_if_none (V4).

    With ``old`` given (an upgrade of ``stable`` to a tag not installed yet), ``look()`` always downloads,
    the pin moves only if it names ``old``, and nothing is removed. With ``keep_old`` nothing is removed.
    """

    def __init__(  # noqa: PLR0913 (the steps' arguments and V4's two options)
        self,
        store: ToolStore,
        name: str,
        lookup: Lookup,
        fetch: Fetch,
        *,
        keep_old: bool = False,
        old: Build | None = None,
    ) -> None:
        super().__init__(store, name, lookup, fetch)
        self.old: Build | None = old  # the build that was compared (V4, step 3)
        self.keep_old = keep_old or old is not None
        self._given_old = old is not None
        self.pin_moved = False
        self.removed: Build | None = None
        self._out: TmpFolder | None = None

    def look(self) -> bool:
        """True: the newest installed build of the name is not what upstream publishes now."""
        self.release = self.lookup(self.name)
        if self._given_old:
            return True
        installed = self._installed_of_name()
        self.old = installed[0] if installed else None
        return self.old is None or not same_as_published(self.old, self.release)

    def move_pin(self) -> None:
        """Move the pin to the new build only if, read now, it names ``old`` (V1, V4)."""
        if self.build is None or self.old is None:
            return
        pinned = _pinned(self.store)
        if pinned is not None and pinned.id == self.old.id and pinned.id != self.build.id:
            self.store.pin(self.build)
            self.pin_moved = True

    def move_old_out(self) -> None:
        """Take ``old`` out of the store if it is still installed and is not the build just added."""
        if self.keep_old or self.old is None or self.build is None or self.old.id == self.build.id:
            return
        self._out = self.store.move_out(self.old)  # None if it has gone meanwhile: the store re-checks
        if self._out is not None:
            self.removed = self.old

    def delete_old(self) -> None:
        if self._out is not None:
            self.store.delete_out(self._out)
            self._out = None


class Uninstall(_Locked):
    """``uninstall()``'s steps: take_store_lock, clean_tmp, move_out, delete_out, clear_pin, release_store_lock.

    ``groups`` holds one group per argument the user gave, each with the builds that argument matched;
    with None, each build is a group of its own. Under the lock, a group none of whose builds is still
    installed is ``missing``, and then nothing at all is removed (V3, question Q8).
    """

    def __init__(
        self, store: ToolStore, builds: Sequence[Build], *, groups: Sequence[Sequence[Build]] | None = None
    ) -> None:
        super().__init__(store)
        self.builds = list({build.id: build for build in builds}.values())
        self.groups = [list(group) for group in groups] if groups is not None else [[build] for build in self.builds]
        self.removed: list[Build] = []
        self.failed: list[tuple[Build, TlaupError]] = []  # could not be moved out (V3, step 1)
        self.missing: list[Build] = []  # the builds of a group with none left under the lock
        self.unpinned: Build | None = None  # the pinned build, when it was removed and the pin cleared
        self._pinned: Build | None = None  # the pinned build, read under the lock before the removals
        self._out: list[TmpFolder] = []

    def move_out(self) -> None:
        """Check every group under the lock, then move each build still installed out, with no short circuit."""
        installed = {(build.id, build.name, build.sha256) for build in self.store.builds()}

        def present(build: Build) -> bool:
            return (build.id, build.name, build.sha256) in installed

        self.missing = [build for group in self.groups if not any(map(present, group)) for build in group]
        if self.missing:
            return
        self._pinned = _pinned(self.store)
        for build in self.builds:
            if not present(build):
                continue  # gone meanwhile; its group still matches others
            try:
                out = self.store.move_out(build)
            except FileOperationError as error:
                self.failed.append((build, error))
                continue
            if out is not None:
                self.removed.append(build)
                self._out.append(out)

    def delete_out(self) -> None:
        """Delete what was moved out. What cannot be deleted stays under ``.tmp/``, unlocked, for ``clean_tmp``."""
        while self._out:
            self.store.delete_out(self._out.pop(0))

    def clear_pin(self) -> None:
        """Clear the pin if, read now, it names a build this command removed; it never moves (V3, step 2)."""
        try:
            self.store.pinned()  # an installed build, or nothing: not one this command removed
        except PinnedBuildMissing:
            # The pin names a missing build. It is one this command removed only if it named one when read
            # under the lock before the removals: the lock has been held since, so no other tlaup wrote it.
            removed = {build.id for build in self.removed}
            if self._pinned is not None and self._pinned.id in removed:
                self.store.unpin()
                self.unpinned = self._pinned


class Pin(_Locked):
    """``pin()``'s steps: take_store_lock, write_pin, release_store_lock."""

    def __init__(self, store: ToolStore, build: Build) -> None:
        super().__init__(store)
        self.build = build

    def write_pin(self) -> bool:
        """False: the build is no longer installed, read now (V1, finding K2-1)."""
        current = _installed(self.store, self.build)
        if current is None:
            return False
        self.store.pin(current)
        return True


# ---------------------------------------------------------------------- install()


@dataclass(frozen=True)
class InstallReport:
    build: Build
    downloaded: bool  # a download was made
    already_installed: bool  # the store already held this name and these bytes
    pinned: bool  # this call pinned it
    could_not_check: str | None  # the reason, when the build was installed and GitHub could not be asked
    matches: tuple[Build, ...] = ()  # every installed build a build spec or a bare CalVer matched, when more than one


def _spec_text(spec: VersionSpec) -> str:
    """The spec as the user typed it, near enough for a message."""
    if spec.name is None:
        return spec.calver or ""
    part = spec.commit or spec.calver or (f"sha256:{spec.sha256}" if spec.sha256 else None)
    return spec.name if part is None else f"{spec.name}@{part}"


def _candidates(matched: Sequence[Build], every: Sequence[Build]) -> str:
    return ", ".join(format_build(build, every) for build in matched)


def _name_only(name: str) -> VersionSpec:
    return VersionSpec(name, None, None, None)


class _Restart(Exception):  # noqa: N818 (a signal inside install(), never raised out of it)
    """The build that was found has gone under the lock: start again."""


def install(  # noqa: PLR0913 (V12's signature)
    store: ToolStore,
    remote: Remote,
    client: GitHubClient,
    spec: VersionSpec,
    *,
    force: bool = False,
    progress: Progress | None = None,
) -> InstallReport:
    """Install what ``spec`` names (V12): already there, downloaded and added, or repaired with ``force``.

    The first build installed is pinned; an existing pin never moves. ``latest`` and addresses never get
    here: ``parse_version_spec`` refuses them.
    """
    while True:
        try:
            return _install_once(store, remote, client, spec, force=force, progress=progress)
        except _Restart:
            continue


def _install_once(  # noqa: PLR0913 (install()'s arguments)
    store: ToolStore,
    remote: Remote,
    client: GitHubClient,
    spec: VersionSpec,
    *,
    force: bool,
    progress: Progress | None,
) -> InstallReport:
    def fetch(release: Release, dest: Path) -> tuple[Path, JarInfo]:
        return fetch_build(client, release, dest, progress)

    is_build_spec = spec.name is None or spec.commit is not None or spec.calver is not None or spec.sha256 is not None
    if not is_build_spec and spec.name is not None:
        return _install_name(store, remote, spec.name, fetch, force=force)
    every = store.builds()
    matched = store.find(spec)
    if spec.name is None and force:
        message = f"--force needs a name to download, and {spec.calver} is a build time"
        hint = f"name one build: {_candidates(matched, every)}" if matched else "name a release such as `rolling`"
        raise UsageError(message, hint=hint)
    if matched and not force:
        if len(matched) > 1:
            return InstallReport(
                matched[0], downloaded=False, already_installed=True, pinned=False, could_not_check=None,
                matches=tuple(matched),
            )  # fmt: skip
        return _found(store, matched[0])
    if len(matched) > 1:
        message = f"{_spec_text(spec)} matches {len(matched)} installed builds, and --force repairs one"
        raise UsageError(message, hint=f"name one of {_candidates(matched, every)}")
    if matched:
        return _repair(store, remote, matched[0], fetch, every)
    if spec.name is None or spec.sha256 is not None:
        message = f"{_spec_text(spec)} is not installed"
        hint = "this form names installed builds only; run `tlaup tool list --installed` to see them"
        raise VersionNotFound(message, hint=hint)
    return _install_build_of_name(store, remote, spec, fetch)


def _first_then_fresh(remote: Remote, first: Release) -> Lookup:
    """A lookup that answers its first call with ``first`` and asks upstream again on a restart (K2-5)."""
    answers = [first]

    def lookup(name: str) -> Release:
        return answers.pop() if answers else remote.release(name)

    return lookup


def _found(store: ToolStore, build: Build) -> InstallReport:
    """A build found installed with no request: pinned when nothing is, if it is still there under the lock."""
    step = Install(store, build.name, _never_looked_up, _never_fetched)  # look() and download() are not called
    step.build = build
    step.take_store_lock()
    try:
        step.clean_tmp()
        if not step.add():
            raise _Restart
        step.pin_if_none()
    finally:
        step.release_store_lock()
    return InstallReport(
        _added(step), downloaded=False, already_installed=True, pinned=step.pinned, could_not_check=None
    )


def _never_looked_up(name: str) -> Release:
    what = f"no request is made for {name}"
    raise _out_of_order(what)


def _never_fetched(release: Release, _dest: Path) -> tuple[Path, JarInfo]:
    what = f"no download is made for {release.tag}"
    raise _out_of_order(what)


def _added(step: Install) -> Build:
    if step.build is None:
        what = "a report before add()"
        raise _out_of_order(what)
    return step.build


def _install_name(store: ToolStore, remote: Remote, name: str, fetch: Fetch, *, force: bool) -> InstallReport:
    """A plain name: looked up fresh, then the steps; an installed build when GitHub cannot be asked."""
    try:
        release = remote.resolve(_name_only(name))
    except _CANNOT_ASK as error:
        installed = store.find(_name_only(name))
        if force or not installed:
            raise
        report = _found(store, installed[0])
        return replace(report, could_not_check=error.message)
    return _run(Install(store, release.tag, _first_then_fresh(remote, release), fetch, force=force))


def _repair(store: ToolStore, remote: Remote, build: Build, fetch: Fetch, every: Sequence[Build]) -> InstallReport:
    """``--force`` on one named build: repaired only if upstream still publishes its bytes (V12)."""
    release = remote.resolve(_name_only(build.name))

    def check(info: _Identity) -> None:
        if info.sha256 != build.sha256:
            printed = format_build(build, every)
            message = (
                f"{printed} is installed and cannot be downloaded again: upstream now publishes another build "
                f"under {release.tag}; {printed} was left as it is"
            )
            hint = f"`tlaup tool install --force {release.tag}` installs what upstream publishes now"
            raise VersionNotFound(message, hint=hint)

    lookup = _first_then_fresh(remote, release)
    return _run(Install(store, release.tag, lookup, fetch, force=True), check)


def _install_build_of_name(store: ToolStore, remote: Remote, spec: VersionSpec, fetch: Fetch) -> InstallReport:
    """``NAME@COMMIT`` or ``NAME@CALVER`` not installed: only if upstream publishes that build now."""
    release = remote.resolve(_name_only(spec.name or ""))

    def check(info: _Identity) -> None:
        if spec.commit is not None:
            ok = info.commit is not None and info.commit.startswith(spec.commit)
        else:
            ok = info.calver == spec.calver
        if not ok:
            now = info.commit[:7] if info.commit else (info.calver or f"sha256:{info.sha256[:12]}")
            message = f"{_spec_text(spec)} is not what upstream publishes: {release.tag} is {release.tag}@{now} now"
            hint = "an older build of a moving tag cannot be downloaded again"
            raise VersionNotFound(message, hint=hint)

    return _run(Install(store, release.tag, _first_then_fresh(remote, release), fetch), check)


def _run(step: Install, check: Callable[[_Identity], None] | None = None) -> InstallReport:
    """The steps in order (V12, step 5); on any error after lock_tmp, give_up before the error leaves.

    ``check`` is applied to the verified jar, or, when nothing is downloaded, to the build found installed.
    """
    while True:
        if step.look():
            step.lock_tmp()
            try:
                step.make_tmp()
                step.download()
                if check is not None and step.info is not None:
                    check(step.info)
                step.take_store_lock()
            except BaseException:
                step.give_up()
                raise
        else:
            if check is not None and step.build is not None:
                check(step.build)  # upstream publishes an installed build, but not the one asked for
            step.take_store_lock()
        try:
            step.clean_tmp()
            if not step.add():
                step.release_store_lock()
                continue  # the build that was found has gone (K2-5): start again, downloading this time
            step.pin_if_none()
        except BaseException:
            step.give_up()
            step.release_store_lock()
            raise
        step.release_store_lock()
        step.release_tmp()
        return InstallReport(
            _added(step), downloaded=step.downloaded, already_installed=step.already_installed, pinned=step.pinned,
            could_not_check=None,
        )  # fmt: skip


# ---------------------------------------------------------------------- upgrade()


@dataclass(frozen=True)
class UpgradeReport:
    name: str  # the name that was upgraded (for `stable`, the tag it resolved to)
    build: Build  # the newest build of the name after the call
    old: Build | None  # the build that was compared; None when the name was not installed
    up_to_date: bool  # nothing was downloaded: `old` is what upstream publishes
    installed: InstallReport | None  # set when no build of the name was installed and upgrade was install
    pin_moved: bool  # the pin named `old` under the lock and now names `build`
    removed: Build | None  # `old`, when this call removed it
    remaining: tuple[Build, ...]  # the other builds of the name still installed, for the note (V4, step 4)
    failed: TlaupError | None = None  # `old` could not be removed; the upgrade itself is done (V4 step 4, V3)


def upgrade(  # noqa: PLR0913 (install()'s arguments and V4's option)
    store: ToolStore,
    remote: Remote,
    client: GitHubClient,
    spec: VersionSpec | None,
    *,
    keep_old: bool = False,
    progress: Progress | None = None,
) -> UpgradeReport:
    """Move a name forward to what upstream publishes now (V4): the pin follows only the build compared.

    ``None`` is the pinned build's name. A build spec is a usage error: a build does not move.
    """
    while True:
        try:
            return _upgrade_once(store, remote, client, spec, keep_old=keep_old, progress=progress)
        except _Restart:
            continue


def _upgrade_name(store: ToolStore, spec: VersionSpec | None) -> str:
    """The name to upgrade (V4, step 1), before any request."""
    if spec is None:
        pinned = store.pinned()  # PinnedBuildMissing for a pin naming a missing build
        if pinned is not None:
            return pinned.name
        if store.builds():
            message = "no version pinned"
            raise NoPinnedBuild(message, hint="name the one to upgrade, for example `tlaup tool upgrade rolling`")
        message = "no TLA+ tools installed"
        raise NoToolsInstalled(message, hint="run `tlaup tool install stable` or `tlaup tool install rolling`")
    if spec.name is None or spec.commit is not None or spec.calver is not None or spec.sha256 is not None:
        message = f"{_spec_text(spec)} names one build, and upgrade moves a name forward"
        names = sorted({build.name for build in store.find(spec)})
        if names:
            hint = " or ".join(f"`tlaup tool upgrade {name}`" for name in names)
        else:
            hint = "name a release such as `rolling` or `stable`"
        raise UsageError(message, hint=hint)
    return spec.name


def _upgrade_once(  # noqa: PLR0913 (upgrade()'s arguments)
    store: ToolStore,
    remote: Remote,
    client: GitHubClient,
    spec: VersionSpec | None,
    *,
    keep_old: bool,
    progress: Progress | None,
) -> UpgradeReport:
    name = _upgrade_name(store, spec)

    def fetch(release: Release, dest: Path) -> tuple[Path, JarInfo]:
        return fetch_build(client, release, dest, progress)

    if name == STABLE:
        release = remote.resolve(_name_only(STABLE))  # a fresh list (V8)
        lookup = _first_then_fresh(remote, release)
        if not any(build.name == release.tag for build in store.builds()):
            return _stable_beside(store, release, lookup, fetch)
        name = release.tag
    else:
        installed = store.find(_name_only(name))  # a tag as typed, then with `v` (V2)
        if not installed:
            return _installed_by_upgrade(install(store, remote, client, _name_only(name), progress=progress))
        name = installed[0].name
        lookup = remote.release  # fresh, never the lookup cache (V4, step 2)
    step = Upgrade(store, name, lookup, fetch, keep_old=keep_old)
    if step.look():
        return _run_upgrade(step)
    return _up_to_date(step)


def _stable_beside(store: ToolStore, release: Release, lookup: Lookup, fetch: Fetch) -> UpgradeReport:
    """``stable`` resolved to a tag with no build installed: beside the installed stable builds (V4, step 1)."""
    stable = store.find(_name_only(STABLE))
    tag_key, old_key = version_key(release.tag), version_key(stable[0].name) if stable else None
    if stable and tag_key is not None and old_key is not None and tag_key > old_key:
        step = Upgrade(store, release.tag, lookup, fetch, keep_old=True, old=stable[0])
        step.look()  # always true with ``old`` given
        return _run_upgrade(step, beside_stable=True)
    return _installed_by_upgrade(_run(Install(store, release.tag, lookup, fetch)))


def _installed_by_upgrade(report: InstallReport) -> UpgradeReport:
    """No build of the name was installed, so upgrade was install (V4, step 1); the name is upstream's tag."""
    return UpgradeReport(
        name=report.build.name, build=report.build, old=None, up_to_date=False,
        installed=report, pin_moved=False, removed=None, remaining=(),
    )  # fmt: skip


def _up_to_date(step: Upgrade) -> UpgradeReport:
    """Nothing to download: under the lock, refresh the ``prerelease`` flag and the source record (V4, step 3)."""
    step.build = step.old
    step.take_store_lock()
    try:
        step.clean_tmp()
        if not step.add():
            raise _Restart  # the build compared has gone meanwhile: start again
        remaining = _remaining(step)
    finally:
        step.release_store_lock()
    build = _upgraded(step)
    return UpgradeReport(
        name=step.name, build=build, old=step.old, up_to_date=True, installed=None, pin_moved=False, removed=None,
        remaining=remaining,
    )  # fmt: skip


def _run_upgrade(step: Upgrade, *, beside_stable: bool = False) -> UpgradeReport:
    """The steps after a ``look()`` that was true (V4, step 4); on any error after lock_tmp, give_up first."""
    step.lock_tmp()
    try:
        step.make_tmp()
        step.download()
        step.take_store_lock()
    except BaseException:
        step.give_up()
        raise
    try:
        step.clean_tmp()
        step.add()  # always true: there is a download
        step.move_pin()
        failed: TlaupError | None = None
        try:
            step.move_old_out()
        except FileOperationError as error:
            failed = error  # a failed removal does not hide a finished upgrade; `old` stays as it was
        step.delete_old()
        remaining = _stable_remaining(step) if beside_stable else _remaining(step)
    except BaseException:
        step.give_up()
        step.release_store_lock()
        raise
    step.release_store_lock()
    step.release_tmp()
    return UpgradeReport(
        name=step.name, build=_upgraded(step), old=step.old, up_to_date=False, installed=None,
        pin_moved=step.pin_moved, removed=step.removed, remaining=remaining, failed=failed,
    )  # fmt: skip


def _upgraded(step: Upgrade) -> Build:
    if step.build is None:
        what = "a report before add()"
        raise _out_of_order(what)
    return step.build


def _remaining(step: Upgrade) -> tuple[Build, ...]:
    """The other builds of the name still installed, read under the lock."""
    kept = step.build.id if step.build is not None else None
    return tuple(build for build in step.store.builds() if build.name == step.name and build.id != kept)


def _stable_remaining(step: Upgrade) -> tuple[Build, ...]:
    """Beside ``stable``: every installed stable build but the new one, read under the lock (V4, "them")."""
    kept = step.build.id if step.build is not None else None
    return tuple(
        build
        for build in step.store.builds()
        if build.id != kept and not build.prerelease and version_key(build.name) is not None
    )


# ---------------------------------------------------------------------- uninstall()


@dataclass(frozen=True)
class UninstallReport:
    removed: tuple[Build, ...]
    failed: tuple[tuple[Build, TlaupError], ...]  # each failure, in the order of the builds given
    missing: tuple[Build, ...]  # non-empty: nothing was removed (V3, under the lock)
    unpinned: Build | None  # the pinned build, when it was removed and the pin cleared


def uninstall(
    store: ToolStore, builds: Sequence[Build], *, groups: Sequence[Sequence[Build]] | None = None
) -> UninstallReport:
    """Remove every build given, with no short circuit, under the lock (V3, D50's order).

    ``groups`` is one group per argument the user gave; with None each build is its own. A group none of
    whose builds is still installed removes nothing at all. The pin is cleared, never moved, when it named
    a build that was removed.
    """
    step = Uninstall(store, builds, groups=groups)
    step.take_store_lock()
    try:
        step.clean_tmp()
        step.move_out()
        step.delete_out()
        step.clear_pin()
    finally:
        step.release_store_lock()
    return UninstallReport(
        removed=tuple(step.removed), failed=tuple(step.failed), missing=tuple(step.missing), unpinned=step.unpinned
    )


# ---------------------------------------------------------------------- pin() and the which-build question


def pin(store: ToolStore, spec: VersionSpec, ui: Ui) -> Build:
    """Pin the build ``spec`` names (V4); several: ask on a terminal, else ``AmbiguousVersion``."""
    found = store.find(spec)
    if not found:
        message = f"{_spec_text(spec)} is not installed"
        raise VersionNotFound(message, hint="run `tlaup tool list --installed` to see the installed builds")
    every = store.builds()
    build = found[0]
    if len(found) > 1:
        if not ui.is_interactive():
            message = f"{_spec_text(spec)} matches {len(found)} installed builds"
            raise AmbiguousVersion(message, hint=f"name one: {_candidates(found, every)}")
        build = choose_build(ui, "Which build should be pinned?", found, allow_all=False, every=every)[0]
    step = Pin(store, build)
    step.take_store_lock()
    try:
        written = step.write_pin()
    finally:
        step.release_store_lock()
    if not written:
        message = f"{format_build(build, every)} is no longer installed"
        raise VersionNotFound(message, hint="another tlaup removed it; run `tlaup tool list --installed`")
    return build


def choose_build(
    ui: Ui, question: str, builds: Sequence[Build], *, allow_all: bool, every: Sequence[Build]
) -> list[Build]:
    """List ``builds`` numbered from 1 in their printed form, on stderr, and ask which (V3's table).

    The answer is a whole number in range, or ``all`` when ``allow_all``; anything else asks again, and an
    empty line too, since there is no default. ``every`` is every installed build, for the printed form.
    """
    for number, build in enumerate(builds, start=1):
        ui.note(f"  {number}. {format_build(build, every)}")
    choices = [str(number) for number in range(1, len(builds) + 1)]
    if allow_all:
        choices.append("all")
    answer = ui.ask(question, choices=choices, default=None)
    return list(builds) if answer == "all" else [builds[int(answer) - 1]]
