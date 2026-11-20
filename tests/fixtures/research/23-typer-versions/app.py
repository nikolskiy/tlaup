"""Tiny app built as design F10 describes (root group subclass mapping errors to the D29 codes,
Console subclass whose on_broken_pipe raises BrokenPipeError, and main() with the closed-pipe measures)."""
import enum
import errno
import os
import select
import stat
import sys
import threading
import time
from contextlib import contextmanager

import typer
import typer.core
from rich.console import Console

try:
    TyperException = typer.TyperException
    TE_SOURCE = "typer.TyperException (public)"
except AttributeError:  # older Typer: the usage-error base class is Click's ClickException
    try:
        from click import ClickException as TyperException
        TE_SOURCE = "click.ClickException (Click is a dependency)"
    except ImportError:  # bundled Click, name not yet public
        from typer._click.exceptions import ClickException as TyperException
        TE_SOURCE = "typer._click.exceptions.ClickException (private)"


class Shell(str, enum.Enum):
    bash = "bash"
    zsh = "zsh"


class TlaupError(Exception):
    exit_code = 3


class PipeConsole(Console):
    def on_broken_pipe(self) -> None:
        raise BrokenPipeError


out = PipeConsole(highlight=False)
err = PipeConsole(stderr=True, highlight=False)
own_exit = threading.local()
DEBUG = bool(os.environ.get("APP_DEBUG"))


def silence(stream):
    try:
        fd = stream.fileno()
    except Exception:
        return
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, fd)
    os.close(devnull)


def is_null_device(fd):
    try:
        return os.path.samestat(os.fstat(fd), os.stat(os.devnull))
    except OSError:
        return False


def reader_gone(fd):
    try:
        if not stat.S_ISFIFO(os.fstat(fd).st_mode):
            return False
        p = select.poll()
        p.register(fd, select.POLLOUT)
        return any(ev & (select.POLLERR | select.POLLHUP) for _, ev in p.poll(0))
    except Exception:
        return False


def report(code, message):
    err.print(f"error: {message}")
    return code


def reported(code, message):
    try:
        report(code, message)
    except BrokenPipeError:
        silence(sys.stderr)
        return 141
    except OSError:
        silence(sys.stderr)
    return code


WRITE_ERRNOS = {errno.ENOSPC, errno.EDQUOT, errno.EFBIG, errno.EIO}


@contextmanager
def mapped():
    try:
        yield
    except typer.Exit:
        own_exit.seen = True
        raise
    except (TyperException, KeyboardInterrupt):
        raise
    except typer.Abort:
        raise typer.Exit(130) from None
    except TlaupError as e:
        raise typer.Exit(reported(e.exit_code, str(e))) from None
    except BrokenPipeError:
        silence(sys.stdout)
        raise typer.Exit(141) from None
    except EOFError:
        raise typer.Exit(reported(3, "input ended")) from None
    except OSError as e:
        if e.filename is None and e.errno in WRITE_ERRNOS:
            silence(sys.stdout)
            raise typer.Exit(reported(5, f"cannot write output: {e.strerror}")) from None
        raise typer.Exit(reported(5, f"internal error: {type(e).__name__}: {e}")) from None
    except Exception as e:
        raise typer.Exit(reported(5, f"internal error: {type(e).__name__}: {e}")) from None


class AppGroup(typer.core.TyperGroup):
    def make_context(self, info_name, args, parent=None, **extra):
        with mapped():
            return super().make_context(info_name, args, parent=parent, **extra)

    def invoke(self, ctx):
        with mapped():
            return super().invoke(ctx)


def version_cb(value: bool):
    if value:
        if os.environ.get("APP_VERSION_RAISES"):
            raise RuntimeError("boom in eager callback")
        out.print("app 1.0")
        raise typer.Exit()


def complete_builds(incomplete: str):
    return [b for b in ("rolling", "rolling@bc1b506", "v1.8.0", "v1.7.4") if b.startswith(incomplete)]


app = typer.Typer(cls=AppGroup, name="app", add_completion=False, no_args_is_help=True,
                  pretty_exceptions_enable=False, help="A tiny app.", epilog="See the manual for more.")
tool = typer.Typer(no_args_is_help=True, help="Tool group.")
app.add_typer(tool, name="tool")


@app.callback()
def root(version: bool = typer.Option(False, "--version", "-V", callback=version_cb, is_eager=True,
                                      help="Show version.")):
    pass


@tool.command("pin")
def pin(build: str = typer.Argument(..., autocompletion=complete_builds, help="A build.")):
    """Pin a build. 'nosuch' raises a domain error (3)."""
    if build == "nosuch":
        raise TlaupError("no such build: nosuch")
    out.print(f"pinned {build}")


@app.command()
def lines(n: int = typer.Option(3, help="How many lines.", envvar="APP_N"),
          shell: Shell = typer.Option(Shell.bash, help="A shell.", rich_help_panel="Extras")):
    """Print N lines through the Rich console."""
    for i in range(n):
        out.print(f"line {i}")


@app.command()
def boom():
    """Raise RuntimeError."""
    raise RuntimeError("unexpected")


@app.command()
def interrupt():
    """Raise KeyboardInterrupt."""
    raise KeyboardInterrupt


@app.command()
def abort():
    """Raise typer.Abort."""
    raise typer.Abort()


@app.command()
def eof():
    """Raise EOFError."""
    raise EOFError


@app.command("exit")
def exit_(code: int = typer.Argument(1)):
    """Exit through typer.Exit."""
    raise typer.Exit(code)


@app.command()
def badparam():
    """Raise typer.BadParameter."""
    raise typer.BadParameter("bad one")


@app.command()
def prompt():
    """typer.prompt on stdin at end of input."""
    typer.prompt("name")


@app.command()
def spin():
    """Print lines without end (for SIGINT)."""
    i = 0
    while True:
        out.print(f"line {i}")
        i += 1
        time.sleep(0.01)


@app.command()
def wait():
    """Sleep (for SIGINT)."""
    sys.stdout.write("ready\n")
    sys.stdout.flush()
    time.sleep(30)


def exit_code_of(leaving: SystemExit) -> int:
    c = leaving.code
    if c is None:
        return 0
    return c if isinstance(c, int) else 1


def main() -> None:
    own_exit.seen = False
    stdout_was_null = is_null_device(1)
    code = 0
    try:
        app(prog_name="app")
    except SystemExit as leaving:
        code = exit_code_of(leaving)
        if code == 1 and not own_exit.seen and (
            (is_null_device(1) and not stdout_was_null) or reader_gone(1) or reader_gone(2)
        ):
            code = 141
    except BrokenPipeError:
        code = 141
    except OSError:
        code = 5
    if code in (129, 130, 143):
        silence(sys.stdout)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except BrokenPipeError:
            silence(stream)
            code = code or 141
        except OSError:
            silence(stream)
            code = code or 5
    sys.exit(code)


if __name__ == "__main__":
    if os.environ.get("APP_BARE"):      # baseline: Typer's own behaviour, none of F10's measures in main()
        app(prog_name="app")
    else:
        if os.environ.get("_APP_COMPLETE") and not os.environ.get("APP_NO_INIT"):
            try:
                from typer._completion_classes import completion_init
            except ImportError:
                completion_init = None
            if completion_init:
                completion_init()
        main()
