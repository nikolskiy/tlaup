"""What build a run uses when the user has not said: the pin, an error naming the next command, or the first install.

Design 12 V9. Everything printed goes through the ``Ui`` given.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tlaup.errors import CannotAsk, NoPinnedBuild, NoToolsInstalled, UsageError, VersionNotFound
from tlaup.versioning.install import install
from tlaup.versioning.order import stable_of
from tlaup.versioning.spec import VersionSpec, format_build

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tlaup.ui import Ui
    from tlaup.versioning.github import GitHubClient, Progress
    from tlaup.versioning.remote import Release, Remote
    from tlaup.versioning.store import Build, ToolStore

ENV_NAME = "TLAUP_AUTO_INSTALL"
OPTION_NAME = "--auto-install"
_CHOICES = ("stable", "rolling")


def read_auto_install(option: str | None, env: Mapping[str, str]) -> str | None:
    """The option, else ``TLAUP_AUTO_INSTALL`` (an empty one is unset); ``stable`` or ``rolling``, else UsageError."""
    if option is not None:
        source, value = f"the option {OPTION_NAME}", option
    else:
        source, value = f"the environment variable {ENV_NAME}", env.get(ENV_NAME, "")
        if value == "":
            return None
    if value not in _CHOICES:
        message = f"{source} must be stable or rolling, not {value!r}"
        raise UsageError(message, hint="use `stable` or `rolling`")
    return value


def _cannot_ask() -> CannotAsk:
    return CannotAsk(
        "no TLA+ tools installed",
        hint="run `tlaup tool install stable` or `tlaup tool install rolling`, or set TLAUP_AUTO_INSTALL",
    )


def _day(stamp: str | None) -> str:
    return (stamp or "")[:10]


def _rolling_line(releases: list[Release]) -> str:
    """The rolling line: the jar's own update date, since the release's publication date is its first creation."""
    rolling = next((r for r in releases if r.tag == "rolling" and r.asset is not None), None)
    text = "the newest development build"
    if rolling is not None and rolling.asset is not None:
        text += f", updated {_day(rolling.asset.updated_at)}"
    return text


FIRST_QUESTION = "No TLA+ tools are installed. Which build should tlaup install?"


def choose_first_build(
    remote: Remote, ui: Ui, *, auto_install: str | None, heading: str = FIRST_QUESTION
) -> VersionSpec:
    """``stable`` or ``rolling``: the given answer, or the answer to the question on stderr.

    Asks only when ``ui`` is interactive, after one fresh fetch of the release list; whatever that raises (the
    network error, no stable release) comes out before any question is written. Otherwise CannotAsk.
    ``heading`` is the question's first line; ``tool install`` with builds installed gives its own (V12).
    """
    if auto_install is not None:
        return VersionSpec(name=auto_install, commit=None, calver=None, sha256=None)
    if not ui.is_interactive():
        raise _cannot_ask()
    releases = remote.fetch_releases()
    stable = stable_of(releases)
    if stable is None:
        message = "no stable release is available"
        raise VersionNotFound(message, hint="run `tlaup tool list` to see the releases")
    ui.note(heading)
    published = _day(stable.published_at or stable.created_at)
    ui.note(f"  1) stable   {stable.tag}, released {published}")
    ui.note(f"  2) rolling  {_rolling_line(releases)}")
    answer = ui.ask("Choice", choices=["1", "2"], default="1")
    return VersionSpec(name="stable" if answer == "1" else "rolling", commit=None, calver=None, sha256=None)


def ensure_tools(  # noqa: PLR0913 (V9's signature and the caller's progress bar)
    store: ToolStore,
    remote: Remote,
    client: GitHubClient,
    ui: Ui,
    *,
    auto_install: str | None,
    may_install: bool = True,
    progress: Progress | None = None,
) -> Build:
    """The build a run uses: the pin; or an error naming the next command; or the first install, then the pin."""
    pinned = store.pinned()
    if pinned is not None:
        return pinned
    builds = store.builds()
    if builds:
        names = ", ".join(format_build(build, builds) for build in builds)
        message = "no version pinned"
        raise NoPinnedBuild(message, hint=f"run `tlaup tool pin <one of: {names}>`")
    if not may_install:
        message = "no TLA+ tools installed"
        raise NoToolsInstalled(message, hint="run `tlaup tool install stable` or `tlaup tool install rolling`")
    if auto_install is not None:
        spec = choose_first_build(remote, ui, auto_install=auto_install)
        ui.note(f"Installing {spec.name} from {client.base_url}")
    elif ui.is_interactive():
        spec = choose_first_build(remote, ui, auto_install=None)
    else:
        raise _cannot_ask()
    report = install(store, remote, client, spec, progress=progress)
    return store.pinned() or report.build
