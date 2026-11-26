"""`tlaup tlc SPEC [options] [-- TLC ARGS...]` (design 20 G1, 11 R1 to R11, 23 C1).

The command parses its options, builds the request, calls the preflight, the command builder and one of the two
run functions, prints the preflight's warnings and the run's notes, and exits with the run's code. It does not
enter the run folder, parse, or decide the exit code. Nothing heavy is imported at the top (design 14 F9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from collections.abc import Callable

    from tlaup.context import AppContext
    from tlaup.tlc.runner import RunOutcome
    from tlaup.ui import Ui
    from tlaup.versioning.store import Build

HELP = "Run the TLC model checker on a TLA+ specification."
SPEC_HELP = "The spec: a name such as Spec or a path to Spec.tla."
TLC_ARGS_HELP = (
    "TLC's own arguments, after `--`: tlaup tlc Spec -- -deadlock. Relative paths after `--` are read from the "
    "folder you run tlaup in, -config from the spec's folder; absolute paths are advised."
)
CFG_HELP = "The model's .cfg file, a name or a path (default: TLC's own, Spec.cfg beside the spec)."
WORKERS_HELP = "The number of TLC workers, or auto for one per core (default: the setting tlc.workers)."
COVERAGE_HELP = "Report how often each action and expression was evaluated."
RAW_HELP = "Print TLC's own output unchanged. On Windows a closed output pipe does not stop TLC."
KEEP_HELP = "Keep the run folder when the run is interrupted or crashes after a complete checkpoint."
SHOW_COMMAND_HELP = (
    "Print the command that would run, and run nothing. The printed command does not stop TLC when the terminal "
    "that pasted it is killed; for a long run pasted by hand, replace the -metadir value with a folder of your own."
)
JAVA_OPT_HELP = "An option for the JVM, repeatable: --java-opt=-Xmx8g."
PLAIN_HELP = (
    "Plain output on a terminal too: each line as it arrives, no live view (default: the setting tlc.plain). "
    "No effect with --raw."
)
REFRESH_INTERVAL_HELP = (
    "How often the live view is redrawn, in seconds (default: the setting tlc.refresh_interval, 1.0). "
    "No effect with plain output or --raw."
)
REFRESH_SETTING = "tlc.refresh_interval"
REFRESH_VARIABLE = "TLAUP_TLC_REFRESH_INTERVAL"
REFRESH_MIN, REFRESH_MAX = 0.1, 60.0
AUTO_INSTALL_HELP = "With no tools installed, install this build without asking: stable or rolling."


def tlc(  # noqa: PLR0913, PLR0917 - a command with twelve options takes them as parameters
    ctx: typer.Context,
    spec: str = typer.Argument(..., metavar="SPEC", help=SPEC_HELP, show_default=False),
    tlc_args: Annotated[
        list[str] | None, typer.Argument(metavar="-- TLC ARGS", help=TLC_ARGS_HELP, show_default=False)
    ] = None,
    cfg: str | None = typer.Option(None, "--cfg", metavar="FILE", help=CFG_HELP, show_default=False),
    workers: str | None = typer.Option(None, "--workers", metavar="N|auto", help=WORKERS_HELP, show_default=False),
    coverage: bool = typer.Option(False, "--coverage", help=COVERAGE_HELP),
    raw: bool = typer.Option(False, "--raw", help=RAW_HELP),
    plain: bool = typer.Option(False, "--plain", help=PLAIN_HELP),
    refresh_interval: float | None = typer.Option(
        None,
        "--refresh-interval",
        metavar="SECONDS",
        min=REFRESH_MIN,
        max=REFRESH_MAX,
        help=REFRESH_INTERVAL_HELP,
        show_default=False,
    ),
    keep: bool = typer.Option(False, "--keep", help=KEEP_HELP),
    show_command: bool = typer.Option(False, "--show-command", help=SHOW_COMMAND_HELP),
    java_opt: Annotated[
        list[str] | None, typer.Option("--java-opt", metavar="OPT", help=JAVA_OPT_HELP, show_default=False)
    ] = None,
    auto_install: str | None = typer.Option(
        None, "--auto-install", metavar="stable|rolling", help=AUTO_INSTALL_HELP, show_default=False
    ),
) -> None:
    """Run the TLC model checker on a TLA+ specification."""
    import random
    import sys
    from dataclasses import replace
    from pathlib import Path

    from tlaup.cmd.common import run_build
    from tlaup.cmd.tool._shared import utc_now
    from tlaup.reporters import ReporterOptions, make_reporter
    from tlaup.tlc.command import build_tlc_command
    from tlaup.tlc.invocation import TlcRequest, resolve_tlc_invocation
    from tlaup.tlc.runner import run_tlc, run_tlc_raw
    from tlaup.versioning.first_run import read_auto_install

    app: AppContext = ctx.find_root().obj
    ui = app.ui
    auto = read_auto_install(auto_install, app.env)  # a usage error, before the preflight (02 X1, rule 5)
    interval = read_refresh_interval(refresh_interval, app)  # the same (22 O5, 11 R11 step 0)
    request = TlcRequest(
        spec=spec,
        cfg=cfg,
        workers=workers,
        coverage=coverage,
        raw=raw,
        keep=True if keep else None,
        java_opts=tuple(java_opt or ()),
        extra_args=tuple(tlc_args or ()),
    )
    inv = resolve_tlc_invocation(
        request,
        paths=app.paths,
        settings=app.settings,
        env=app.env,
        cwd=Path.cwd(),
        home=Path.home(),
        get_build=_pinned_build(app) if show_command else run_build(app, auto),
        now=utc_now,
        rng=random.SystemRandom(),
    )
    java_inv = build_tlc_command(inv)
    if show_command:
        argv = replace(java_inv, lifeline=False).argv()  # 11 R9: no lifeline agent (D51)
        line = _join(argv, windows=sys.platform == "win32")
        ui.out.print(line, markup=False, highlight=False, emoji=False, soft_wrap=True)
        return  # never wrapped or read as markup (10 P11); exit 0
    for text in inv.warnings:
        ui.warning(text)
    if request.raw:
        outcome = run_tlc_raw(inv, java_inv, paths=app.paths, now=utc_now, notice=ui.note)
    else:
        reporter = make_reporter(app, ReporterOptions(plain=plain, refresh_interval=interval))
        outcome = run_tlc(inv, java_inv, reporter, paths=app.paths, now=utc_now, notice=ui.note)
    print_run_notes(outcome, ui)
    raise typer.Exit(outcome.exit_code)


def read_refresh_interval(option: float | None, app: AppContext) -> float:
    """The option, else the setting ``tlc.refresh_interval``; from 0.1 to 60 seconds, else UsageError (22 O5).

    The schema checks only that the setting is a number (14 F1, question Q16); the range is the command's, so a value
    from the environment or the config file is a usage error too, naming where it came from. Typer checks the
    option's range itself, so the option is checked here again only as a guard.
    """
    from tlaup.config.loader import EDIT_HINT
    from tlaup.errors import UsageError

    if option is not None:
        source, value, hint = "the option --refresh-interval", option, None
    elif REFRESH_VARIABLE in app.env:  # the environment layer wins over the file (14 F1)
        source, value, hint = f"the environment variable {REFRESH_VARIABLE}", app.settings.tlc.refresh_interval, None
    else:
        source, value = f"config.yaml: {REFRESH_SETTING}", app.settings.tlc.refresh_interval
        hint = EDIT_HINT
    if not REFRESH_MIN <= value <= REFRESH_MAX:  # false for nan too
        message = f"{source} must be from {REFRESH_MIN:g} to {REFRESH_MAX:g} seconds, not {value:g}"
        raise UsageError(message, hint=hint)
    return value


def _join(argv: list[str], *, windows: bool) -> str:
    """One line a shell reads back as ``argv`` (11 R9)."""
    if windows:
        import subprocess

        return subprocess.list2cmdline(argv)
    import shlex

    return shlex.join(argv)


def _pinned_build(app: AppContext) -> Callable[[], Build]:
    """``get_build`` for ``--show-command``: the pin or an error; never asks, installs or sends a request (11 R9).

    The same errors as ``ensure_tools(..., may_install=False)``, with no GitHub client built."""

    def get_build() -> Build:
        from tlaup.cmd.tool._shared import open_store, pinned_build

        return pinned_build(open_store(app))

    return get_build


def print_run_notes(outcome: RunOutcome, ui: Ui) -> None:
    """What a run that returned leaves to say, on stderr (20 G1, 11 R6, 10 P3).

    The kept folder's two lines; or, for a raw run, the checkpoint that was not kept; then, for a parsed run whose
    TLC exit code and verdict disagree, one warning naming both.
    """
    from tlaup.reporters.text import DROPPED_CHECKPOINT
    from tlaup.tlc.rundirs import kept_note

    if outcome.kept is not None:
        for line in kept_note(outcome.kept):
            ui.note(line)
    elif outcome.result is None and outcome.dropped_checkpoint in DROPPED_CHECKPOINT:
        ui.note(DROPPED_CHECKPOINT[outcome.dropped_checkpoint])  # a parsed run's result line already says it
    warning = disagreement(outcome)
    if warning is not None:
        ui.warning(warning)


def disagreement(outcome: RunOutcome) -> str | None:
    """10 P3: the warning when TLC's exit code and the verdict of its output disagree; None when they agree."""
    from tlaup_parse import Verdict

    result, code = outcome.result, outcome.tool_exit_code
    if result is None or code is None or outcome.stopped_by is not None or outcome.stopped_for_closed_pipe:
        return None
    verdict = result.verdict
    if code == 0 and verdict is Verdict.ERRORS:
        count = len(result.errors)
        return f"TLC exited with 0, but its output reports {count} error{'' if count == 1 else 's'}"
    if code == 0 and verdict is Verdict.NOT_CHECKED:
        return "TLC exited with 0, but its output reports that the spec was not checked"
    if code == 0 and verdict is Verdict.INCOMPLETE:
        return "TLC exited with 0, but its output reports an incomplete run"
    if code != 0 and verdict in (Verdict.NO_ERROR, Verdict.NO_ERROR_BOUNDED):
        return f"TLC exited with {code}, but its output reports no error"
    return None
