"""`tlaup tool path [VERSION]` (design 23 C1, 02 X3): one build's jar on one line, for scripts; it never asks."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from tlaup.cmd.completion import complete_installed
from tlaup.errors import AmbiguousVersion

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.ui import Ui
    from tlaup.versioning.spec import VersionSpec
    from tlaup.versioning.store import ToolStore

HELP = "Print the path of a TLA+ tools build's jar: the pinned build's, or the one VERSION names. It never asks."
VERSION_HELP = (
    "An installed build: a tag such as v1.7.4 or 1.7.4, stable, rolling, or tag@commit. Without it, the pinned build."
)


def path_command(
    ctx: typer.Context,
    version: str | None = typer.Argument(
        None, metavar="VERSION", help=VERSION_HELP, show_default=False, autocompletion=complete_installed
    ),
) -> None:
    app: AppContext = ctx.find_root().obj
    from tlaup.cmd.tool._shared import open_store, parse_spec

    store = open_store(app)
    spec = parse_spec(app, store, version) if version is not None else None
    code = show_path(store, app.ui, version, spec)
    if code:
        raise typer.Exit(code)


def show_path(store: ToolStore, ui: Ui, text: str | None, spec: VersionSpec | None) -> int:
    """The jar of the pinned build, or of the one installed build ``spec`` names; several are a usage error."""
    from tlaup.cmd.tool._shared import not_installed, pinned_build, printed

    if spec is None or text is None:
        build = pinned_build(store)
    else:
        found = store.find(spec)
        if not found:
            raise not_installed(text, spec)
        if len(found) > 1:
            every = store.builds()
            names = ", ".join(printed(build, every) for build in found)
            message = f"{text} matches {len(found)} installed builds"
            raise AmbiguousVersion(message, hint=f"name one: {names}")
        build = found[0]
    ui.result(str(build.jar))
    return 0
