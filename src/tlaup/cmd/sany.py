"""`tlaup sany SPEC [-- SANY ARGS...]` (design 21 S1, 23 C1).

The command reads its options, calls the preflight and the command builder, prints the preflight's warnings, gives
the run a sink that prints through the `Ui`, and exits with the run's code. It decides nothing about a line of
SANY's output: the parser classes it and `tools/sany.py` routes it. Nothing heavy is imported at the top (14 F9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from tlaup.cmd.completion import complete_spec

if TYPE_CHECKING:
    from pathlib import Path

    from rich.console import Console

    from tlaup.context import AppContext
    from tlaup.tools.sany import SanyOutcome
    from tlaup.ui import Ui
    from tlaup_parse import Diagnostic

HELP = "Parse a TLA+ specification with SANY and print its errors."
SPEC_HELP = (
    "The spec: a name such as Spec or a path to Spec.tla. SANY reads it from the spec's own folder, and looks for "
    "modules in the spec's folder, then the library folders, then the standard modules, then the classpath."
)
SANY_ARGS_HELP = (
    "SANY's own arguments, after `--`: tlaup sany Spec -- -nopcal. `-d` is refused: it starts an explorer that "
    "waits for input; run it with Java directly on the jar that `tlaup tool path` prints."
)
JAVA_OPT_HELP = "An option for the JVM, repeatable: --java-opt=-Xmx8g."
AUTO_INSTALL_HELP = "With no tools installed, install this build without asking: stable or rolling."


def sany(
    ctx: typer.Context,
    spec: str = typer.Argument(..., metavar="SPEC", help=SPEC_HELP, show_default=False, autocompletion=complete_spec),
    sany_args: Annotated[
        list[str] | None, typer.Argument(metavar="-- SANY ARGS", help=SANY_ARGS_HELP, show_default=False)
    ] = None,
    java_opt: Annotated[
        list[str] | None, typer.Option("--java-opt", metavar="OPT", help=JAVA_OPT_HELP, show_default=False)
    ] = None,
    auto_install: str | None = typer.Option(
        None, "--auto-install", metavar="stable|rolling", help=AUTO_INSTALL_HELP, show_default=False
    ),
) -> None:
    """Parse a TLA+ specification with SANY and print its errors."""
    from pathlib import Path

    from tlaup.cmd.common import run_build
    from tlaup.cmd.tool._shared import utc_now
    from tlaup.tools.invocation import build_tool_command, resolve_tool_invocation
    from tlaup.tools.sany import run_sany
    from tlaup.versioning.first_run import read_auto_install

    app: AppContext = ctx.find_root().obj
    auto = read_auto_install(auto_install, app.env)  # a usage error, before the preflight (02 X1, rule 5)
    inv = resolve_tool_invocation(
        "sany",
        spec,
        java_opts=tuple(java_opt or ()),
        extra_args=tuple(sany_args or ()),
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
    sink = PrintingSink(app.ui, cwd=Path.cwd(), spec=inv.spec)
    outcome = run_sany(inv, build_tool_command(inv), sink, lambda done: app.ui.note(summary(done)))
    raise typer.Exit(outcome.exit_code)


def summary(outcome: SanyOutcome) -> str:
    """S1, step 5: ``no errors``, or the counts, as English needs them (``1 error, 0 warnings``)."""
    diagnostics = outcome.result.diagnostics
    if not diagnostics:
        return "no errors"
    errors = sum(1 for d in diagnostics if d.severity == "error")
    warnings = len(diagnostics) - errors
    return f"{_count(errors, 'error')}, {_count(warnings, 'warning')}"


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def read_source(path: str) -> str | None:
    """A spec file as UTF-8 with undecodable bytes replaced; None when it cannot be read (S1)."""
    from pathlib import Path

    try:
        return Path(path).read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return None


class PrintingSink:
    """What `run_sany` prints through: banner and progress on stderr, anything else and the diagnostics on stdout, as
    text, never as markup and never wrapped (10 P11); a tab stays a tab, as in the excerpt's marks."""

    def __init__(self, ui: Ui, *, cwd: Path, spec: Path | None) -> None:
        self._ui = ui
        self._cwd = cwd
        self._spec = spec

    @staticmethod
    def _write(console: Console, line: str) -> None:
        from rich.text import Text

        from tlaup.reporters.text import AsPrinted

        console.print(AsPrinted(Text(line)), soft_wrap=True, markup=False, highlight=False, emoji=False)

    def chatter(self, line: str) -> None:
        self._write(self._ui.err, line)

    def other(self, line: str) -> None:
        self._write(self._ui.out, line)

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        from tlaup.reporters.text import format_diagnostic

        path = diagnostic.file if diagnostic.file is not None else str(self._spec)
        source = read_source(path) if diagnostic.location is not None else None
        lines = format_diagnostic(diagnostic, cwd=self._cwd, spec=self._spec or self._cwd, source_text=source)
        for line in lines:
            self._write(self._ui.out, line)
