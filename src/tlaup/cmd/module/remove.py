"""`tlaup module remove NAME` (design 13 M1, M2, 23 C1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from tlaup.cmd.completion import complete_module

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.modules.registry import Registry
    from tlaup.ui import Ui

HELP = "Remove a registered module by name."
NAME_HELP = "The name of a registered module, as `tlaup module list` shows it."


def remove_command(
    ctx: typer.Context,
    name: str = typer.Argument(..., metavar="NAME", help=NAME_HELP, show_default=False, autocompletion=complete_module),
) -> None:
    app: AppContext = ctx.find_root().obj
    from tlaup.cmd.module._shared import open_registry

    remove_module(open_registry(app), app.ui, name)


def remove_module(registry: Registry, ui: Ui, name: str) -> None:
    """``InvalidName`` (2) before the disk is touched, ``ModuleNotFound`` (4), ``FileOperationError`` (5)."""
    registry.remove(name)
    ui.note(f"Removed module {name}")
