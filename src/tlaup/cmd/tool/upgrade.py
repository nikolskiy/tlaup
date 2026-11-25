"""`tlaup tool upgrade [VERSION]` (design 12 V4, 23 C1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from tlaup.errors import PinnedBuildMissing

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tlaup.context import AppContext
    from tlaup.ui import Ui
    from tlaup.versioning.github import GitHubClient, Progress
    from tlaup.versioning.install import UpgradeReport
    from tlaup.versioning.remote import Remote
    from tlaup.versioning.spec import VersionSpec
    from tlaup.versioning.store import Build, ToolStore

HELP = (
    "Replace an installed version with the newest build of the same name. Rolling builds are rebuilt often; "
    "this fetches the current one. It does not move to a different version: use `install` for that."
)
VERSION_HELP = "The name to upgrade, such as rolling, stable or v1.8.0; with none, the pinned build's name."


def upgrade_command(
    ctx: typer.Context,
    version: str | None = typer.Argument(None, metavar="VERSION", help=VERSION_HELP, show_default=False),
) -> None:
    app: AppContext = ctx.find_root().obj
    from tlaup.cmd.tool._shared import download_progress, open_remote, open_store, parse_spec

    store = open_store(app)
    spec = parse_spec(app, store, version) if version is not None else None
    client, remote = open_remote(app)
    with download_progress(app.ui) as progress:
        code = upgrade_tools(store, remote, client, app.ui, spec, progress=progress)
    if code:
        raise typer.Exit(code)


def upgrade_tools(  # noqa: PLR0913 (the store, the remote, the client, the Ui and the parsed arguments)
    store: ToolStore,
    remote: Remote,
    client: GitHubClient,
    ui: Ui,
    spec: VersionSpec | None,
    *,
    progress: Progress | None,
) -> int:
    """Move a name forward (V4); 5 when the upgrade is done but the old build could not be removed."""
    from tlaup.cmd.tool._shared import printed
    from tlaup.versioning.install import upgrade

    report = upgrade(store, remote, client, spec, progress=progress)
    every = store.builds()
    new = printed(report.build, every)
    if report.installed is not None:
        ui.note(f"{report.name} was not installed; installed {new}")
        if report.installed.pinned:
            ui.note(f"Pinned {new}")
        return 0
    if report.up_to_date:
        ui.note(f"{new} is up to date")
        return 0
    _say_upgraded(store, ui, report, every, beside_stable=spec is not None and spec.name == "stable")
    if report.failed is not None:
        old = printed(report.old, [*every, report.old]) if report.old is not None else report.name
        ui.note(f"{old} was not removed: {report.failed.message}")
        return 5
    return 0


def _say_upgraded(
    store: ToolStore, ui: Ui, report: UpgradeReport, every: Sequence[Build], *, beside_stable: bool
) -> None:
    from tlaup.cmd.tool._shared import joined, printed

    new = printed(report.build, every)
    before = [*every, *(build for build in (report.old,) if build is not None and build not in every)]
    old = printed(report.old, before) if report.old is not None else None
    if old is None or beside_stable:
        ui.note(f"Installed {new}" + (", the newest stable release" if beside_stable else ""))
    else:
        ui.note(f"Upgraded {old} to {new}")
    if report.pin_moved:
        ui.note(f"Pinned {new}")
    if report.removed is not None and old is not None:
        ui.note(f"Removed {old}")
    try:
        pinned = store.pinned()
    except PinnedBuildMissing:
        pinned = None
    if pinned is not None and pinned.name == report.build.name and pinned.id != report.build.id:
        ui.note(f"{printed(pinned, every)} is still pinned (tlaup tool pin {new})")
    unremoved = report.old.id if report.failed is not None and report.old is not None else None
    remaining = [printed(build, every) for build in report.remaining if build.id != unremoved]  # its own line
    if not remaining:
        return
    if beside_stable:
        ui.note(f"Still installed: {joined(remaining)}")
        return
    count = len(remaining)
    builds = "build" if count == 1 else "builds"
    verb = "is" if count == 1 else "are"
    ui.note(
        f"{count} older {builds} of {report.build.name} {verb} still installed ({joined(remaining)}); "
        "`tlaup tool uninstall` removes them"
    )
