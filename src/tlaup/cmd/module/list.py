"""`tlaup module list` (design 13 M2, 14 F8, 23 C1): the registered modules and when each was built, in UTC."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import typer  # noqa: TC002 - Typer reads the annotations when it registers the command

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.modules.registry import Registry
    from tlaup.ui import Ui

HELP = "List the registered modules with the time each was built, in UTC."
NOTHING_REGISTERED = "no modules are registered"


def list_command(ctx: typer.Context) -> None:
    app: AppContext = ctx.find_root().obj
    from tlaup.cmd.module._shared import open_registry

    list_modules(open_registry(app), app.ui)


def built_time(built_at: str) -> str:
    """``2026-11-15T10:00:00Z`` as ``2026-11-15 10:00 UTC``; a text that is not a time is shown as it is."""
    try:
        built = datetime.strptime(built_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return built_at
    return built.strftime("%Y-%m-%d %H:%M UTC")


def list_modules(registry: Registry, ui: Ui) -> None:
    """One row per registered module in name order on stdout; with none, an empty stdout and a note."""
    from rich.table import Table

    from tlaup.cmd.tool._shared import print_table

    modules = registry.list()
    if not modules:
        ui.note(NOTHING_REGISTERED)
        return
    table = Table()
    table.add_column("Module", no_wrap=True)
    table.add_column("Built", no_wrap=True)
    for module in modules:
        table.add_row(module.name, built_time(module.built_at))
    print_table(ui, table)
