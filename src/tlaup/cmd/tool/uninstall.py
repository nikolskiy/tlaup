"""`tlaup tool uninstall [VERSION]... [--all] [--yes]` (design 12 V3, 23 C1)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from tlaup.errors import ConflictingOptions, UsageError, VersionNotFound

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tlaup.context import AppContext
    from tlaup.ui import Ui
    from tlaup.versioning.install import UninstallReport
    from tlaup.versioning.spec import VersionSpec
    from tlaup.versioning.store import Build, ToolStore

HELP = (
    "Remove installed TLA+ tools builds. A VERSION that matches several builds asks which on a terminal, "
    "and removes all of them with --yes or without a terminal."
)
VERSIONS_HELP = "The builds to remove: a tag, stable, rolling, or tag@commit for one build."
ALL_HELP = "Remove every installed build."
YES_HELP = "Answer every question of this command with yes."
WHICH = "Which build should be removed (a number, or all)?"


def uninstall_command(
    ctx: typer.Context,
    versions: Annotated[
        list[str] | None, typer.Argument(metavar="VERSION", help=VERSIONS_HELP, show_default=False)
    ] = None,
    all_builds: bool = typer.Option(False, "--all", help=ALL_HELP),
    yes: bool = typer.Option(False, "--yes", help=YES_HELP),
) -> None:
    app: AppContext = ctx.find_root().obj
    from tlaup.cmd.tool._shared import open_store, parse_spec

    store = open_store(app)
    named = [(text, parse_spec(app, store, text)) for text in versions or []]
    code = uninstall_tools(store, app.ui, named, all_builds=all_builds, yes=yes)
    if code:
        raise typer.Exit(code)


def uninstall_tools(
    store: ToolStore, ui: Ui, named: Sequence[tuple[str, VersionSpec]], *, all_builds: bool, yes: bool
) -> int:
    """V3: resolve every argument first, then ask, then remove; 5 when a build could not be removed."""
    from tlaup.versioning.install import uninstall

    if named and all_builds:
        message = "name the builds to remove, or give --all, not both"
        raise ConflictingOptions(message, hint="`tlaup tool uninstall --all` removes every installed build")
    if not named and not all_builds:
        message = "name the builds to remove, or give --all"
        raise UsageError(message, hint="run `tlaup tool uninstall <version>` or `tlaup tool uninstall --all`")
    every = store.builds()
    if all_builds:
        if not every:
            ui.note("no builds are installed")
            return 0
        if not _confirmed(ui, len(every), yes=yes):
            ui.note("nothing removed")
            return 0
        groups = [every]
    else:
        groups = _chosen(store, ui, named, every, yes=yes)
    report = uninstall(store, [build for group in groups for build in group], groups=groups)
    if report.missing:
        if all_builds:
            ui.note("no builds are installed")
            return 0
        gone = {build.id for build in report.missing}
        texts = [text for (text, _), group in zip(named, groups, strict=True) if all(b.id in gone for b in group)]
        raise _not_installed(texts, again=True)
    return _say(store, ui, report, every)


def _confirmed(ui: Ui, count: int, *, yes: bool) -> bool:
    if yes:
        return True
    if not ui.is_interactive():
        message = "`--all` asks for confirmation and there is no terminal; add `--yes`"
        raise UsageError(message)
    builds = "build" if count == 1 else "builds"
    return ui.ask(f"Remove all {count} installed {builds} (y/n)?", choices=["y", "n"], default="n") == "y"


def _chosen(
    store: ToolStore, ui: Ui, named: Sequence[tuple[str, VersionSpec]], every: list[Build], *, yes: bool
) -> list[list[Build]]:
    """One group per argument: every argument resolved before any question, and a question only on a terminal."""
    from tlaup.versioning.install import choose_build

    found = [(text, store.find(spec)) for text, spec in named]
    missing = [text for text, matched in found if not matched]
    if missing:
        raise _not_installed(missing)
    groups = []
    for _, matched in found:
        if len(matched) > 1 and not yes and ui.is_interactive():
            matched = choose_build(ui, WHICH, matched, allow_all=True, every=every, default="all")  # noqa: PLW2901
        groups.append(matched)
    return groups


def _not_installed(texts: Sequence[str], *, again: bool = False) -> VersionNotFound:
    from tlaup.cmd.tool._shared import joined

    verb = "is" if len(texts) == 1 else "are"
    message = f"{joined(list(texts))} {verb} not installed"
    if again:
        message = f"{joined(list(texts))} {verb} no longer installed (another tlaup removed it); nothing was removed"
    return VersionNotFound(message, hint="run `tlaup tool list --installed` to see the installed builds")


def _say(store: ToolStore, ui: Ui, report: UninstallReport, every: list[Build]) -> int:
    from tlaup.cmd.tool._shared import printed

    for build in report.removed:
        ui.note(f"Removed {printed(build, every)}")
    for build, error in report.failed:
        ui.note(f"{printed(build, every)} was not removed: {error.message}")
    if report.unpinned is not None:
        ui.note(f"{printed(report.unpinned, every)} was pinned; nothing is pinned now")
        left = store.builds()
        if left:
            names = ", ".join(printed(build, left) for build in left)
            ui.note(f"run `tlaup tool pin <one of: {names}>` to pin another")
    return 5 if report.failed else 0
