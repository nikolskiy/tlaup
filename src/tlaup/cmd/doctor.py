"""`tlaup doctor` (design 23 C1): one line per check, and exit 3 when any is an error."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer  # noqa: TC002 (typer reads the annotation of `ctx` at run time)

if TYPE_CHECKING:
    from tlaup.context import AppContext

HELP = (
    "Check the setup tlaup relies on, one line per check.\n\n"
    "It checks Java, javac, the pinned build, the config file and the folders tlaup uses, and prints ok, warning or "
    "error for each. It re-runs the Java version checks and rewrites the remembered answers. "
    "Exits 3 when a check is an error. It makes no request and changes nothing else."
)


def doctor(ctx: typer.Context) -> None:
    app_context: AppContext = ctx.find_root().obj
    from tlaup.cmd.tool._shared import utc_now
    from tlaup.doctor import run_checks
    from tlaup.errors import NotSetUp

    checks = run_checks(app_context.paths, app_context.env, now=utc_now)
    for check in checks:
        app_context.ui.result(f"{check.name}: {check.level}, {check.detail}")
        if check.hint is not None:
            app_context.ui.result(f"  {check.hint}")
    failed = sum(1 for check in checks if check.level == "error")
    if failed:
        noun = "check" if failed == 1 else "checks"
        raise NotSetUp(f"{failed} {noun} failed")  # noqa: TRY003
