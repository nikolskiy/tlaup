"""What the `tool` commands build the same way: the store, the client and remote, the progress bar, the version.

Package 39 builds the same three for the run commands from here, so the token and the repository are read in
one place. Nothing heavy is imported at the top (design 14 F9).
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from tlaup.errors import ConfigInvalid, NoPinnedBuild, NoToolsInstalled, VersionNotFound

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from tlaup.context import AppContext
    from tlaup.ui import Ui
    from tlaup.versioning.github import GitHubClient, Progress
    from tlaup.versioning.remote import Remote
    from tlaup.versioning.spec import VersionSpec
    from tlaup.versioning.store import Build, ToolStore

LATEST = "latest"


def utc_now() -> datetime:
    """The real clock, aware and in UTC: what every store and remote of a command is given."""
    return datetime.now(UTC)


def open_store(ctx: AppContext) -> ToolStore:
    from tlaup.versioning.store import ToolStore

    return ToolStore(ctx.paths, now=utc_now)


def _user_agent() -> str:
    import importlib.metadata

    try:
        return f"tlaup/{importlib.metadata.version('tlaup')}"
    except importlib.metadata.PackageNotFoundError:
        return "tlaup"


def open_remote(ctx: AppContext) -> tuple[GitHubClient, Remote]:
    """The client for ``tool.repository`` with the token from the environment, and the remote over it."""
    from tlaup.versioning.github import GitHubClient, token_from_env
    from tlaup.versioning.remote import Remote

    settings = ctx.settings.tool
    client = GitHubClient(
        settings.repository,
        token=token_from_env(ctx.env),
        token_hosts=settings.token_hosts,
        user_agent=_user_agent(),
    )
    return client, Remote(client, ctx.paths.remote, now=utc_now)


def latest_tag(ctx: AppContext, store: ToolStore) -> str | None:
    """The tag to name after `stable` in the refusal of `latest` (02 X3): never a request.

    The stable release of the cached list, whatever its age, when a cache file exists; else the highest-numbered
    installed build that is not a prerelease; else None. A broken config file only hides the cached list.
    """
    from tlaup.versioning.order import stable_of
    from tlaup.versioning.spec import VersionSpec

    try:
        _, remote = open_remote(ctx)
        cached = remote.cached()
    except ConfigInvalid:
        cached = None
    if cached is not None:
        stable = stable_of(cached)
        if stable is not None:
            return stable.tag
    installed = store.find(VersionSpec("stable", None, None, None))
    return installed[0].name if installed else None


def parse_spec(ctx: AppContext, store: ToolStore, text: str) -> VersionSpec:
    """``parse_version_spec``, with the tag of `stable` in the refusal of `latest`."""
    from tlaup.versioning.spec import latest_refused, parse_version_spec

    if text.partition("@")[0] == LATEST:
        raise latest_refused(latest_tag(ctx, store))
    return parse_version_spec(text)


def printed(build: Build, every: Sequence[Build]) -> str:
    """A build in the form that, typed back, finds exactly it among ``every``, the installed builds (02 X3)."""
    from tlaup.versioning.spec import format_build

    return format_build(build, every)


def pinned_build(store: ToolStore) -> Build:
    """The pinned build, for ``tool current`` and ``tool path``; NoPinnedBuild, NoToolsInstalled or
    PinnedBuildMissing (3) when there is none to show."""
    build = store.pinned()  # PinnedBuildMissing for a pin that names no installed build
    if build is not None:
        return build
    every = store.builds()
    if every:
        names = ", ".join(printed(other, every) for other in every)
        message = "no version pinned"
        raise NoPinnedBuild(message, hint=f"run `tlaup tool pin <one of: {names}>`")
    message = "no TLA+ tools installed"
    raise NoToolsInstalled(message, hint="run `tlaup tool install stable` or `tlaup tool install rolling`")


def not_installed(text: str, spec: VersionSpec) -> VersionNotFound:
    """``VersionNotFound`` for a spec no installed build matches, naming ``tool install`` where it names a release."""
    names_a_release = spec.name is not None and spec.sha256 is None
    hint = (
        f"run `tlaup tool install {text}` to install it, or `tlaup tool list --installed` to see what is"
        if names_a_release
        else "run `tlaup tool list --installed` to see the installed builds"
    )
    return VersionNotFound(f"{text} is not installed", hint=hint)


def joined(names: Sequence[str]) -> str:
    """``a``, ``a and b``, ``a, b and c``."""
    if len(names) <= 1:
        return "".join(names)
    return f"{', '.join(names[:-1])} and {names[-1]}"


class _Bar:
    """The download's bar on stderr, from the first byte to the last, so a call that downloads nothing shows none."""

    def __init__(self, ui: Ui) -> None:
        self._ui = ui
        self._bar: Any = None
        self._task: Any = None

    def _start(self, done: int, total: int | None) -> None:
        from rich import filesize
        from rich.progress import BarColumn, DownloadColumn, Progress, ProgressColumn, TextColumn
        from rich.text import Text

        class Speed(ProgressColumn):
            """Rich's transfer speed; for a jar that arrives in one piece, the average since the first byte."""

            def render(self, task: Any) -> Text:
                speed = task.finished_speed or task.speed
                if speed is None and task.finished_time:
                    speed = task.completed / task.finished_time
                return Text("?" if speed is None else f"{filesize.decimal(int(speed))}/s")

        self._bar = Progress(TextColumn("tla2tools.jar"), BarColumn(), DownloadColumn(), Speed(), console=self._ui.err)
        self._task = self._bar.add_task("download", total=total, completed=done)
        self._bar.start()

    def __call__(self, done: int, total: int | None) -> None:
        if self._bar is None:
            self._start(done, total)
        self._bar.update(self._task, completed=done, total=total)
        if total is not None and done >= total:
            # Stopped once the bytes are in, so the notes that follow print below it. A download that did not
            # verify is made again from 0 (V5): that call starts a new bar.
            self.stop()

    def stop(self) -> None:
        if self._bar is not None:
            self._bar.stop()
            self._bar = None


def _no_progress(_done: int, _total: int | None) -> None:
    return None


@contextmanager
def download_progress(ui: Ui) -> Iterator[Progress]:
    """A progress callback: a bar on ``ui.err`` when it is a terminal, nothing otherwise."""
    if not ui.err.is_terminal:
        yield _no_progress
        return
    bar = _Bar(ui)
    try:
        yield bar
    finally:
        bar.stop()
