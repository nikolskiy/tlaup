"""`tlaup tool pin VERSION` (design 12 V4, 23 C1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from tlaup.cmd.completion import complete_installed

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.ui import Ui
    from tlaup.versioning.spec import VersionSpec
    from tlaup.versioning.store import ToolStore

HELP = "Pin the TLA+ tools build that runs use. A VERSION that matches several builds asks which on a terminal."
VERSION_HELP = "An installed build: a tag such as v1.7.4 or 1.7.4, stable, rolling, or tag@commit."


def pin_command(
    ctx: typer.Context,
    version: str = typer.Argument(
        ..., metavar="VERSION", help=VERSION_HELP, show_default=False, autocompletion=complete_installed
    ),
) -> None:
    app: AppContext = ctx.find_root().obj
    from tlaup.cmd.tool._shared import open_store, parse_spec

    store = open_store(app)
    code = pin_tools(store, app.ui, version, parse_spec(app, store, version))
    if code:
        raise typer.Exit(code)


def pin_tools(store: ToolStore, ui: Ui, text: str, spec: VersionSpec) -> int:
    """Pin the build ``spec`` names; asks which on a terminal when several match (V4)."""
    from tlaup.cmd.tool._shared import not_installed, printed
    from tlaup.versioning.install import pin

    if not store.find(spec):
        raise not_installed(text, spec)
    build = pin(store, spec, ui)
    ui.note(f"Pinned {printed(build, store.builds())}")
    return 0
