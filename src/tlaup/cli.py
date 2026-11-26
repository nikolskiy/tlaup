"""TLA+ CLI tool - entry point, and the one place errors become messages and exit codes (design 14 F10)."""

import importlib.metadata
import os
import sys
import traceback
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from typing import Any, NoReturn

import typer
from typer.core import TyperGroup

from tlaup.cmd.check_java import check_java
from tlaup.cmd.config import app as config_app
from tlaup.cmd.module import app as module_app
from tlaup.cmd.tlc import tlc as run_tlc_cmd
from tlaup.cmd.tool import app as tool_app
from tlaup.context import AppContext, build_context
from tlaup.errors import CannotAsk, Failed, TlaupError
from tlaup.stdio import WRITE_ERRNOS, closed_pipe_on_windows, is_null_device, reader_gone, silence
from tlaup.ui import Ui
from tlaup.versioning.app_version import get_app_version
from tlaup.versioning.redact import redact


class _OwnExit:
    """Whether a `typer.Exit` passed through `mapped` in this run: a 1 a command asked for is never made 141."""

    seen: bool = False


own_exit = _OwnExit()


def _debug_text(text: str) -> str:
    """Every line printed under debug goes through the debug filter: no token, no query string (12 V7)."""
    return redact(text, os.environ)


def _plain(text: str) -> str:
    return text


def _debug_on(ctx: typer.Context | None, args: Sequence[str]) -> bool:
    """Not from the application context, which the failure may have stopped from being built."""
    if os.environ.get("TLAUP_DEBUG") == "1":
        return True
    if ctx is not None:
        return bool(ctx.find_root().params.get("debug"))
    for word in args:  # make_context failed: --debug among the root's options, before the first other word
        if not word.startswith("-"):
            break
        if word == "--debug":
            return True
    return False


def _ui_for(ctx: typer.Context | None) -> Ui:
    root = ctx.find_root().obj if ctx is not None else None
    return root.ui if isinstance(root, AppContext) else Ui.for_process()


def _traceback_of(error: BaseException) -> str:
    return "".join(traceback.format_exception(error)).rstrip("\n")


def _print_notes(ui: Ui, error: BaseException, text: Callable[[str], str]) -> None:
    for note in getattr(error, "__notes__", ()):
        ui.note(text(str(note)))


def _finish(ui: Ui, error: BaseException, debug: bool) -> None:
    """The notes; under debug the traceback instead, which ends with the notes itself."""
    if debug:
        ui.note(_debug_text(_traceback_of(error)))
    else:
        _print_notes(ui, error, _plain)


def print_notes(error: BaseException, ctx: typer.Context | None, args: Sequence[str] = ()) -> None:
    """The exception's notes alone, on stderr: what a closed pipe still says."""
    text = _debug_text if _debug_on(ctx, args) else _plain
    _print_notes(_ui_for(ctx), error, text)


def report(error: TlaupError, ctx: typer.Context | None, args: Sequence[str]) -> None:
    """`error:`, `hint:`, the details, the notes; under debug the traceback after them."""
    ui = _ui_for(ctx)
    debug = _debug_on(ctx, args)
    text = _debug_text if debug else _plain
    ui.error(
        text(error.message),
        hint=None if error.hint is None else text(error.hint),
        details=None if error.details is None else text(error.details),
    )
    _finish(ui, error, debug)


def _issues_address() -> str | None:
    """From the package metadata's project URLs, so the address is written in one place."""
    try:
        urls = importlib.metadata.metadata("tlaup").get_all("Project-URL") or []
    except importlib.metadata.PackageNotFoundError:
        return None
    for entry in urls:
        label, _, address = str(entry).partition(",")
        if label.strip() == "Issues":
            return address.strip()
    return None


def report_internal_error(error: BaseException, ctx: typer.Context | None, args: Sequence[str]) -> None:
    """A bug: `error: internal error: <type>: <message>` and a hint naming --debug, TLAUP_DEBUG and the issues."""
    ui = _ui_for(ctx)
    debug = _debug_on(ctx, args)
    text = _debug_text if debug else _plain
    name = type(error).__name__
    message = f"internal error: {name}: {error}" if str(error) else f"internal error: {name}"
    hint = 'run it again as "tlaup --debug ..." or with TLAUP_DEBUG=1'
    address = _issues_address()
    if address is not None:
        hint += f", and report it at {address}"
    ui.error(text(message), hint=text(hint))
    _finish(ui, error, debug)


def reported(code: int, report_it: Callable[..., None], *args: Any) -> int:
    """Print the error; if stderr itself cannot be written, say nothing more and keep a sensible code."""
    try:
        report_it(*args)
    except BrokenPipeError:  # stderr is the pipe that closed
        silence(sys.stderr)
        return 141
    except OSError:  # stderr is on a full disk; the error's own code stands
        silence(sys.stderr)
    return code


@contextmanager
def mapped(
    *,
    ctx: typer.Context | None = None,
    args: Sequence[str] = (),
    closed_pipe: Callable[[OSError], bool] = closed_pipe_on_windows,
) -> Iterator[None]:
    """Turn every exception that leaves the root group into one report and an exit code (design 14 F10)."""
    try:
        yield
    except typer.Exit:
        own_exit.seen = True  # an exit a command asked for, the wrapped tool's code among them
        raise
    except (typer.TyperException, KeyboardInterrupt):
        raise  # Typer's own: usage errors (2), Ctrl-C (130)
    except typer.Abort:
        raise typer.Exit(130) from None  # Ctrl-C at a prompt that is not Ui.ask
    except TlaupError as e:
        raise typer.Exit(reported(e.exit_code, report, e, ctx, args)) from None
    except BrokenPipeError as e:
        silence(sys.stdout)
        raise typer.Exit(reported(141, print_notes, e, ctx, args)) from None  # nothing else for a closed pipe
    except EOFError as e:
        error = CannotAsk("the input ended while tlaup was waiting for an answer")
        error.__cause__ = e
        raise typer.Exit(reported(3, report, error, ctx, args)) from None
    except OSError as e:
        if closed_pipe(e):  # decision D57: Windows reports a closed pipe as EINVAL
            silence(sys.stdout)
            raise typer.Exit(reported(141, print_notes, e, ctx, args)) from None
        if e.filename is None and e.errno in WRITE_ERRNOS:  # a write to a stream that is already open failed
            silence(sys.stdout)
            failed = Failed(f"cannot write output: {e.strerror}")
            failed.__cause__ = e
            raise typer.Exit(reported(5, report, failed, ctx, args)) from None
        raise typer.Exit(reported(5, report_internal_error, e, ctx, args)) from None
    except Exception as e:  # noqa: BLE001, RUF100 - the one allowed blind except (30 I8); RUF100 until 58 turns BLE on
        raise typer.Exit(reported(5, report_internal_error, e, ctx, args)) from None


class TlaupGroup(TyperGroup):
    """The root group: the mapping wraps both steps Typer takes here, parsing the root options and running."""

    @staticmethod
    def closed_pipe(e: OSError) -> bool:
        """The closed-pipe rule for Windows; a test subclass answers for a platform it does not run on."""
        return closed_pipe_on_windows(e)

    def make_context(self, info_name: str | None, args: list[str], parent: Any = None, **extra: Any) -> Any:
        with mapped(args=list(args), closed_pipe=self.closed_pipe):  # no context yet
            return super().make_context(info_name, args, parent=parent, **extra)

    def invoke(self, ctx: Any) -> Any:
        with mapped(ctx=ctx, closed_pipe=self.closed_pipe):
            return super().invoke(ctx)


def _exit_code_of(leaving: SystemExit) -> int:
    if leaving.code is None:
        return 0
    if isinstance(leaving.code, int):
        return leaving.code
    return 1  # a message given to sys.exit; Python exits 1 for it


def run_app(app: typer.Typer) -> NoReturn:
    """Run the app as the process and exit with its code: a closed pipe is 141, a full disk 5 (design 14 F10)."""
    own_exit.seen = False  # this may run twice in one process
    stdout_was_null = is_null_device(1)
    code = 0
    try:
        app(prog_name="tlaup")  # always leaves by SystemExit
    except SystemExit as leaving:
        code = _exit_code_of(leaving)
        if (
            code == 1
            and not own_exit.seen  # never a 1 that a command asked for
            and (
                (is_null_device(1) and not stdout_was_null)  # Rich's own closed-pipe handling ran
                or reader_gone(1)
                or reader_gone(2)  # a stream is a pipe nobody reads
            )
        ):
            code = 141
    except BrokenPipeError:  # Typer's own printing, outside the group
        code = 141
    except OSError as e:  # the same, on a full disk: its message could not be written
        code = 141 if closed_pipe_on_windows(e) else 5
    if code in (129, 130, 143):  # stopped by a signal: do not wait for a reader
        silence(sys.stdout)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except BrokenPipeError:
            silence(stream)
            code = code or 141
        except OSError as e:  # a full disk under a redirect, or Windows' closed pipe
            silence(stream)
            code = code or (141 if closed_pipe_on_windows(e) else 5)
    sys.exit(code)


app = typer.Typer(
    cls=TlaupGroup,
    name="tlaup",
    help="TLA+ tools: download TLA+ toolset distribution, compile custom modules, run model checker.",
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_enable=False,
)


def version_callback(value: bool) -> None:
    if value:
        meta = importlib.metadata.metadata("tlaup")
        app_ver = get_app_version(base_version=meta["Version"])
        ui = Ui.for_process()  # eager: runs before the root callback has built the context
        ui.result(f"{meta['Name']} v{app_ver}")
        ui.result(meta["Summary"])
        raise typer.Exit()


@app.callback()
def root(
    ctx: typer.Context,
    _: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
    debug: bool = typer.Option(False, "--debug", help="Show the full traceback when an error occurs."),
) -> None:
    """TLA+ CLI tool."""
    ctx.obj = build_context(os.environ, debug=debug)


# --- Subcommands ---


app.add_typer(module_app, name="module")
app.add_typer(tool_app, name="tool")
app.add_typer(config_app, name="config")

app.command(name="tlc")(run_tlc_cmd)
app.command(name="check-java")(check_java)


def main() -> None:
    """Entry point for [project.scripts] and `python -m tlaup`."""
    run_app(app)
