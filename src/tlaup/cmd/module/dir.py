"""`tlaup module dir` (design 23 C1, 14 F2): the modules folder in effect, whether or not it exists."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer  # noqa: TC002 - Typer reads the annotations when it registers the command

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.ui import Ui

HELP = "Print the folder that holds the registered modules."


def dir_command(ctx: typer.Context) -> None:
    app: AppContext = ctx.find_root().obj  # no setting is read, so a broken config file does not matter
    show_dir(app, app.ui)


def show_dir(app: AppContext, ui: Ui) -> int:
    ui.result(str(app.paths.modules))
    return 0
