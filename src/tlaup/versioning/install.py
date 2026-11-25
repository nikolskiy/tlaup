"""Install, upgrade, uninstall and pin as steps (design 12 V1, V3, V4, V11, V12).

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
from typing import TYPE_CHECKING

from tlaup.errors import (
    FileOperationError,
    InternalError,
    NetworkError,
    PinnedBuildMissing,
    RateLimited,
    RemoteDataError,
    UsageError,
    VersionNotFound,
)
from tlaup.versioning.download import fetch_build, usable_digest
from tlaup.versioning.jarinfo import JarInfo
from tlaup.versioning.remote import Release
from tlaup.versioning.spec import VersionSpec, format_build
from tlaup.versioning.store import Source

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tlaup.errors import TlaupError
    from tlaup.versioning.github import GitHubClient, Progress
    from tlaup.versioning.remote import Remote
    from tlaup.versioning.store import Build, TmpFolder, ToolStore

Lookup = Callable[[str], Release]  # what upstream publishes under a name now (V8)
Fetch = Callable[[Release, Path], tuple[Path, JarInfo]]  # fetch_build with the client bound (V5)

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

    def check(info: JarInfo) -> None:
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

    def check(info: JarInfo) -> None:
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


def _run(step: Install, check: Callable[[JarInfo], None] | None = None) -> InstallReport:
    """The steps in order (V12, step 5); on any error after lock_tmp, give_up before the error leaves."""
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
