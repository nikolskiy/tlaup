"""`tlaup tool install [VERSION] [--force]` (design 12 V12, 23 C1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from tlaup.cmd.completion import complete_install
from tlaup.errors import PinnedBuildMissing, UsageError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from tlaup.context import AppContext
    from tlaup.ui import Ui
    from tlaup.versioning.github import GitHubClient, Progress
    from tlaup.versioning.install import InstallReport
    from tlaup.versioning.remote import Remote
    from tlaup.versioning.spec import VersionSpec
    from tlaup.versioning.store import Build, ToolStore

HELP = (
    "Download and install a TLA+ tools build. With no VERSION, asks whether to install `stable` or `rolling`. "
    "The first build installed is pinned."
)
VERSION_HELP = "A tag such as v1.7.4 or 1.7.4, stable, rolling, or tag@commit for one build."
FORCE_HELP = "Download the build again even when it is installed, and repair it in place."
INSTALLED_HEADING = "Which build should tlaup install?"


def install_command(
    ctx: typer.Context,
    version: str | None = typer.Argument(
        None, metavar="VERSION", help=VERSION_HELP, show_default=False, autocompletion=complete_install
    ),
    force: bool = typer.Option(False, "--force", help=FORCE_HELP),
) -> None:
    app: AppContext = ctx.find_root().obj
    from tlaup.cmd.tool._shared import download_progress, open_remote, open_store, parse_spec

    store = open_store(app)
    spec = parse_spec(app, store, version) if version is not None else None
    check_arguments(store, app.ui, spec, force=force, env=app.env)  # before the settings are loaded
    client, remote = open_remote(app)
    with download_progress(app.ui) as progress:
        code = install_tools(store, remote, client, app.ui, spec, force=force, env=app.env, progress=progress)
    if code:
        raise typer.Exit(code)


def install_tools(  # noqa: PLR0913 (the store, the remote, the client, the Ui and the parsed arguments)
    store: ToolStore,
    remote: Remote,
    client: GitHubClient,
    ui: Ui,
    spec: VersionSpec | None,
    *,
    force: bool,
    env: Mapping[str, str],
    progress: Progress | None,
) -> int:
    """Install what ``spec`` names, or with no version the build the question or TLAUP_AUTO_INSTALL chooses."""
    from tlaup.versioning.first_run import choose_first_build, read_auto_install
    from tlaup.versioning.install import install

    check_arguments(store, ui, spec, force=force, env=env)
    if spec is None:
        auto = read_auto_install(None, env)
        if store.builds():
            spec = choose_first_build(remote, ui, auto_install=auto, heading=INSTALLED_HEADING)
        else:
            spec = choose_first_build(remote, ui, auto_install=auto)
    report = install(store, remote, client, spec, force=force, progress=progress)
    _say(store, ui, report, force=force)
    return 0


def check_arguments(store: ToolStore, ui: Ui, spec: VersionSpec | None, *, force: bool, env: Mapping[str, str]) -> None:
    """The usage errors of the command line alone, raised before any setting is read or request made."""
    from tlaup.cmd.tool._shared import printed
    from tlaup.versioning.first_run import ENV_NAME, read_auto_install

    if spec is None:
        if read_auto_install(None, env) is None and not ui.is_interactive():
            message = "no version given, and there is no terminal to ask which build to install"
            hint = f"run `tlaup tool install stable` or `tlaup tool install rolling`, or set {ENV_NAME}"
            raise UsageError(message, hint=hint)
    elif force and spec.name is None:
        every = store.builds()
        matched = store.find(spec)
        message = f"--force needs a name to download, and {spec.calver} is a build time"
        names = ", ".join(printed(build, every) for build in matched)
        raise UsageError(message, hint=f"name one build: {names}" if matched else "name a release such as `rolling`")


def _say(store: ToolStore, ui: Ui, report: InstallReport, *, force: bool) -> None:
    from tlaup.cmd.tool._shared import joined, printed

    every = store.builds()
    new = printed(report.build, every)
    if report.matches:
        names = [printed(build, every) for build in report.matches]
        ui.note(f"{joined(names)} are already installed")
        return
    if report.could_not_check is not None:
        ui.warning(f"could not check GitHub for a newer build of {report.build.name}: {report.could_not_check}")
    elif report.already_installed and force:
        ui.note(f"Reinstalled {new}")
    elif report.already_installed:
        ui.note(f"{new} is already installed (use --force to download it again)")
    else:
        _say_added(store, ui, report, every)
    if report.pinned:
        ui.note(f"Pinned {new}")


def _say_added(store: ToolStore, ui: Ui, report: InstallReport, every: Sequence[Build]) -> None:
    from tlaup.cmd.tool._shared import joined, printed

    new = printed(report.build, every)
    others = [build for build in every if build.name == report.build.name and build.id != report.build.id]
    try:
        pinned = store.pinned()
    except PinnedBuildMissing:
        pinned = None
    if pinned is not None and any(build.id == pinned.id for build in others):
        ui.note(f"{new} installed; {printed(pinned, every)} is still pinned (tlaup tool pin {new})")
    elif others:
        beside = joined([printed(build, every) for build in others])
        if report.pinned:
            ui.note(f"{new} installed beside {beside}")  # the "Pinned" line follows
        else:
            shown = printed(pinned, every) if pinned is not None else None
            ui.note(f"{new} installed beside {beside}; " + (f"{shown} is pinned" if shown else "nothing is pinned"))
    else:
        ui.note(f"Installed {new}")
