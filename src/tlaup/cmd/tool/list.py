"""`tlaup tool list [--installed]` (design 12 V8 "`tool list` in the first wave", 02 X4, decisions D64, D65)."""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

import typer

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tlaup.context import AppContext
    from tlaup.ui import Ui
    from tlaup.versioning.remote import Release, Remote
    from tlaup.versioning.store import Build, ToolStore

HELP = (
    "List the TLA+ tools releases that have a jar, newest first with rolling at the top, each followed by "
    "its installed builds."
)
INSTALLED_HELP = "List the installed builds only, without asking GitHub."

STALE = "GitHub could not be reached; the release list is the one cached earlier"
UNAVAILABLE = "GitHub could not be reached and no release list is cached; only the installed builds are listed"
NOTHING_INSTALLED = "no builds are installed"
PINNED = "✓"

AVAILABLE = "available"
INSTALLED = "installed"
UPDATE_AVAILABLE = "installed, update available"
NOT_UPSTREAM = "installed, not upstream"


class Row(NamedTuple):
    version: str
    build: str
    published: str
    status: str
    pinned: bool


def list_command(
    ctx: typer.Context,
    installed: bool = typer.Option(False, "--installed", help=INSTALLED_HELP),
) -> None:
    app: AppContext = ctx.find_root().obj
    from tlaup.cmd.tool._shared import open_remote, open_store

    store = open_store(app)
    if installed:
        code = list_installed(store, app.ui)  # no settings, no request
    else:
        _, remote = open_remote(app)
        code = list_tools(store, remote, app.ui)
    if code:
        raise typer.Exit(code)


def list_installed(store: ToolStore, ui: Ui) -> int:
    """The installed builds, in store order, each as installed."""
    builds = store.builds()
    if not builds:
        ui.note(NOTHING_INSTALLED)
        return 0
    pinned = _pinned_id(store)
    _print(ui, [_build_row(build, builds, INSTALLED, pinned) for build in builds])
    return 0


def list_tools(store: ToolStore, remote: Remote, ui: Ui) -> int:
    """The releases with a jar in X4's order, each followed by its installed builds, then those upstream dropped."""
    from tlaup.versioning.remote import Freshness

    releases, freshness = remote.releases()
    if freshness is Freshness.UNAVAILABLE:
        ui.warning(UNAVAILABLE)
        return list_installed(store, ui)
    if freshness is Freshness.STALE:
        ui.note(STALE)
    _print(ui, table_rows(releases, store.builds(), _pinned_id(store)))
    return 0


def table_rows(releases: Sequence[Release], builds: Sequence[Build], pinned: str | None) -> list[Row]:
    """The rows of V8's table, as settled at the stage 4 sign-off (package 29, "What each command does").

    A release row is ``available`` unless an installed build of its name is what upstream publishes; the newest
    installed build of a name is ``installed, update available`` when it is not; a build whose name upstream no
    longer lists is ``installed, not upstream``, last; every other installed build is ``installed``.
    """
    from tlaup.versioning.install import same_as_published
    from tlaup.versioning.order import name_key

    listed = {release.tag for release in releases}
    with_jar: dict[str, Release] = {}
    for release in releases:
        if release.asset is not None:
            with_jar.setdefault(release.tag, release)
    by_name: dict[str, list[Build]] = {}
    for build in builds:
        by_name.setdefault(build.name, []).append(build)  # store order: newest first within a name
    rows: list[Row] = []
    for name in sorted(set(with_jar) | (set(by_name) & listed), key=name_key):
        published = with_jar.get(name)
        installed = by_name.get(name, [])
        if published is not None:
            status = INSTALLED if any(same_as_published(build, published) for build in installed) else AVAILABLE
            rows.append(
                Row(published.tag, "", _date(published.asset.updated_at if published.asset else None), status, False)
            )
        for position, build in enumerate(installed):
            newer = position == 0 and published is not None and not same_as_published(build, published)
            rows.append(_build_row(build, builds, UPDATE_AVAILABLE if newer else INSTALLED, pinned))
    rows.extend(_build_row(build, builds, NOT_UPSTREAM, pinned) for build in builds if build.name not in listed)
    return rows


def _pinned_id(store: ToolStore) -> str | None:
    """The pinned build's id; a pin naming a missing build marks nothing here (``tool current`` says so)."""
    from tlaup.errors import PinnedBuildMissing

    try:
        build = store.pinned()
    except PinnedBuildMissing:
        return None
    return None if build is None else build.id


def _build_row(build: Build, every: Sequence[Build], status: str, pinned: str | None) -> Row:
    """An installed build: under Build the part of its printed form after ``@``, so ``NAME@BUILD`` finds exactly
    it (02 X3), with the CalVer in brackets where it has one and the printed form does not already end in it."""
    from tlaup.cmd.tool._shared import printed

    shown = printed(build, every)
    part = shown.partition("@")[2]
    if build.calver is not None and not shown.endswith(build.calver):
        part = f"{part} ({build.calver})"
    return Row(build.name, part, _date(build.source.asset_updated_at), status, build.id == pinned)


def _date(timestamp: str | None) -> str:
    """The date of one of GitHub's times, ``2026-11-19T18:12:31Z``; nothing when there is none."""
    return "" if not timestamp else timestamp.split("T", maxsplit=1)[0]


def _print(ui: Ui, rows: Sequence[Row]) -> None:
    from rich.table import Table

    table = Table()
    for header in ("Version", "Build", "Published", "Status"):
        table.add_column(header)
    table.add_column("Pinned", justify="center")
    for row in rows:
        table.add_row(row.version, row.build, row.published, row.status, PINNED if row.pinned else "")
    ui.result(table)
