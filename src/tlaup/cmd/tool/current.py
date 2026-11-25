"""`tlaup tool current` (design 23 C1): the pinned build and its jar, with no Java and no network."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.ui import Ui
    from tlaup.versioning.store import ToolStore

HELP = "Show the pinned TLA+ tools build and the path of its jar, without starting Java."


def current_command(ctx: typer.Context) -> None:
    app: AppContext = ctx.find_root().obj
    from tlaup.cmd.tool._shared import open_store

    code = show_current(open_store(app), app.ui)
    if code:
        raise typer.Exit(code)


def show_current(store: ToolStore, ui: Ui) -> int:
    """Two lines on stdout: the pinned build with its build time, and its jar."""
    from tlaup.cmd.tool._shared import pinned_build, printed

    build = pinned_build(store)
    shown = printed(build, store.builds())
    if build.calver is not None and not shown.endswith(build.calver):
        shown = f"{shown} ({build.calver})"
    ui.result(shown)
    ui.result(str(build.jar))
    return 0
