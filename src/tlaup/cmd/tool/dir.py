"""`tlaup tool dir` (design 23 C1): the folder of the installed builds, whether or not it exists."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer  # noqa: TC002 - Typer reads the annotations when it registers the command

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.ui import Ui

HELP = "Print the folder that holds the installed TLA+ tools builds."


def dir_command(ctx: typer.Context) -> None:
    app: AppContext = ctx.find_root().obj
    show_dir(app, app.ui)


def show_dir(app: AppContext, ui: Ui) -> int:
    ui.result(str(app.paths.tools))
    return 0
