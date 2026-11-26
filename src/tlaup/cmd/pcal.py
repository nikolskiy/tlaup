"""`tlaup pcal SPEC [-- TRANSLATOR ARGS...]` (design 21 S2, 23 C1).

The shape of `cmd/sany.py`: read the options, preflight, build the command, print through a sink, exit with the
translator's own code. Nothing heavy is imported at the top (14 F9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

from tlaup.cmd.sany import AUTO_INSTALL_HELP, JAVA_OPT_HELP, PrintingSink

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.tools.pcal import PcalOutcome
    from tlaup_parse import Diagnostic

HELP = "Translate the PlusCal algorithm of a spec to TLA+ with the PlusCal translator."
SPEC_HELP = (
    "The spec: a name such as Spec or a path to Spec.tla. The spec is rewritten in place and the previous version "
    "is kept as SPEC.old; SPEC.cfg is written, or rewritten with no backup (pass `-- -nocfg` to leave it alone). "
    "The translator reads the spec from the spec's own folder."
)
PCAL_ARGS_HELP = "The translator's own arguments, after `--`: tlaup pcal Spec -- -nocfg."


def pcal(
    ctx: typer.Context,
    spec: str = typer.Argument(..., metavar="SPEC", help=SPEC_HELP, show_default=False),
    pcal_args: Annotated[
        list[str] | None, typer.Argument(metavar="-- TRANSLATOR ARGS", help=PCAL_ARGS_HELP, show_default=False)
    ] = None,
    java_opt: Annotated[
        list[str] | None, typer.Option("--java-opt", metavar="OPT", help=JAVA_OPT_HELP, show_default=False)
    ] = None,
    auto_install: str | None = typer.Option(
        None, "--auto-install", metavar="stable|rolling", help=AUTO_INSTALL_HELP, show_default=False
    ),
) -> None:
    """Translate the PlusCal algorithm of a spec to TLA+ with the PlusCal translator."""
    from pathlib import Path

    from tlaup.cmd.common import run_build
    from tlaup.cmd.tool._shared import utc_now
    from tlaup.errors import InternalError
    from tlaup.tools.invocation import build_tool_command, resolve_tool_invocation
    from tlaup.tools.pcal import run_pcal, written_notes
    from tlaup.versioning.first_run import read_auto_install

    app: AppContext = ctx.find_root().obj
    auto = read_auto_install(auto_install, app.env)  # a usage error, before the preflight (02 X1, rule 5)
    cwd = Path.cwd()
    inv = resolve_tool_invocation(
        "pcal",
        spec,
        java_opts=tuple(java_opt or ()),
        extra_args=tuple(pcal_args or ()),
        paths=app.paths,
        settings=app.settings,
        env=app.env,
        cwd=cwd,
        home=Path.home(),
        now=utc_now,
        get_build=run_build(app, auto),
    )
    for text in inv.warnings:
        app.ui.warning(text)
    if inv.spec is None:  # pcal reads a spec: resolve_tool_invocation gives one for it
        message = "the preflight gave no spec for pcal"
        raise InternalError(message)
    spec_path = inv.spec
    sink = PcalPrintingSink(app.ui, cwd=cwd, spec=spec_path)

    def notes(done: PcalOutcome) -> None:
        for note in written_notes(done.result.files_written, spec_path, cwd):
            app.ui.note(note)

    outcome = run_pcal(inv, build_tool_command(inv), sink, notes)
    raise typer.Exit(outcome.exit_code)


class PcalPrintingSink(PrintingSink):
    """`sany`'s sink with the label line added; a diagnostic has no excerpt (S2 step 4)."""

    def label(self, name: str, line: int, column: int) -> None:
        from tlaup.tools.pcal import label_line

        self._write(self._ui.out, label_line(name, line, column, self._spec or self._cwd, self._cwd))

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        from tlaup.reporters.text import format_diagnostic

        for line in format_diagnostic(diagnostic, cwd=self._cwd, spec=self._spec or self._cwd, source_text=None):
            self._write(self._ui.out, line)
