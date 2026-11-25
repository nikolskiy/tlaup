"""`tlaup module add PATH` (design 13 M1 to M3, 23 C1): build the folder and register it under its name."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime
    from pathlib import Path

    from tlaup.context import AppContext
    from tlaup.java.locate import JavaRuntime
    from tlaup.modules.registry import Registry
    from tlaup.ui import Ui
    from tlaup.versioning.store import Build

HELP = "Build a module folder and register it under the folder's name, replacing a module of that name."
PATH_HELP = "A module folder: modules/*.tla, tlc2/overrides/*.java or modules/tlc2/overrides/*.java, lib/*.jar."


def add_command(
    ctx: typer.Context,
    path: str = typer.Argument(..., metavar="PATH", help=PATH_HELP, show_default=False),
) -> None:
    app: AppContext = ctx.find_root().obj
    from pathlib import Path

    from tlaup.cmd.module._shared import open_registry
    from tlaup.cmd.tool._shared import utc_now
    from tlaup.modules.build import source_name

    source = Path(path)
    source_name(source)  # what the user typed is checked before any setting is read (D45's spirit)
    add_module(
        open_registry(app),
        app.ui,
        source,
        get_build=lambda: _pinned_build(app),
        get_javac=lambda: _javac(app),
        release=app.settings.java.min_version,
        now=utc_now,
    )


def _pinned_build(app: AppContext) -> Build:
    """The pinned build or the error: never a question, an install or a request (M2)."""
    from tlaup.cmd.tool._shared import open_remote, open_store
    from tlaup.versioning.first_run import ensure_tools

    store = open_store(app)
    client, remote = open_remote(app)
    return ensure_tools(store, remote, client, app.ui, auto_install=None, may_install=False)


def _javac(app: AppContext) -> JavaRuntime:
    from tlaup.java.locate import require_javac

    return require_javac(app.env, min_version=app.settings.java.min_version, cache_file=app.paths.java_cache)


def add_module(  # noqa: PLR0913 - the registry, the two bound functions, the clock and the arguments
    registry: Registry,
    ui: Ui,
    source: Path,
    *,
    get_build: Callable[[], Build],
    get_javac: Callable[[], JavaRuntime],
    release: int,
    now: Callable[[], datetime],
) -> None:
    """Build and register ``source``; say ``Added`` or ``Replaced``, then the warnings."""
    from tlaup.modules.build import build_module

    built = build_module(source, registry=registry, get_build=get_build, get_javac=get_javac, release=release, now=now)
    ui.note(f"{'Replaced' if built.replaced else 'Added'} module {built.name}")
    for text in built.warnings:
        ui.warning(text)
