"""`tlaup repl [-- ARGS...]` (design 21 S3, 23 C1).

The shape of `cmd/sany.py` with no spec: read the options, preflight, build the command, run the REPL on the
terminal, exit with its own code. Nothing heavy is imported at the top (14 F9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from tlaup.cmd.sany import AUTO_INSTALL_HELP, JAVA_OPT_HELP

if TYPE_CHECKING:
    from tlaup.context import AppContext

HELP = "Start the TLA+ REPL of the pinned build (rolling builds only)."
REPL_ARGS_HELP = "The REPL's own arguments, after `--`: tlaup repl -- ARGS."


def repl(
    ctx: typer.Context,
    repl_args: Annotated[
        list[str] | None, typer.Argument(metavar="-- ARGS", help=REPL_ARGS_HELP, show_default=False)
    ] = None,
    java_opt: Annotated[
        list[str] | None, typer.Option("--java-opt", metavar="OPT", help=JAVA_OPT_HELP, show_default=False)
    ] = None,
    auto_install: str | None = typer.Option(
        None, "--auto-install", metavar="stable|rolling", help=AUTO_INSTALL_HELP, show_default=False
    ),
) -> None:
    """Start the TLA+ REPL of the pinned build (rolling builds only).

    Ctrl-C belongs to the REPL, and SIGTERM stops it from outside. The REPL keeps its history in
    ~/.tlaplus/history.repl, where upstream puts it.
    """
    from pathlib import Path

    from tlaup.cmd.common import run_build
    from tlaup.cmd.tool._shared import utc_now
    from tlaup.tools.invocation import build_tool_command, resolve_tool_invocation
    from tlaup.tools.repl import run_repl
    from tlaup.versioning.first_run import read_auto_install

    app: AppContext = ctx.find_root().obj
    auto = read_auto_install(auto_install, app.env)  # a usage error, before the preflight (02 X1, rule 5)
    inv = resolve_tool_invocation(
        "repl",
        None,
        java_opts=tuple(java_opt or ()),
        extra_args=tuple(repl_args or ()),
        paths=app.paths,
        settings=app.settings,
        env=app.env,
        cwd=Path.cwd(),
        home=Path.home(),
        now=utc_now,
        get_build=run_build(app, auto),
    )
    for text in inv.warnings:
        app.ui.warning(text)
    outcome = run_repl(build_tool_command(inv))
    raise typer.Exit(outcome.exit_code)
