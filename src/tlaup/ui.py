"""Messages: the one place that builds consoles (design 14 F6), beside the four old message functions."""

import contextlib
import os
import sys
from collections.abc import Mapping, Sequence
from typing import Any, TextIO

import typer
from rich.console import Console
from rich.text import Text

from tlaup.errors import CannotAsk


def warn(message: str) -> None:
    """Print a standardized warning message to stderr."""
    typer.echo(f"{typer.style('⚠', fg=typer.colors.YELLOW)} Warning: {message}", err=True)


def error(message: str) -> None:
    """Print a standardized error message to stderr."""
    typer.echo(f"{typer.style('✖', fg=typer.colors.RED)} Error: {message}", err=True)


def info(message: str) -> None:
    """Print a standardized info message to stderr."""
    typer.echo(f"{typer.style('i', fg=typer.colors.CYAN)} Info: {message}", err=True)


def success(message: str) -> None:
    """Print a standardized success message to stderr."""
    typer.echo(f"{typer.style('✔', fg=typer.colors.GREEN)} Success: {message}", err=True)


ColorPolicy = bool | None  # None decides per stream; True always colours; False never does


_INPUT_ENDED = "the input ended while tlaup was waiting for an answer"


class _PipeConsole(Console):
    """The only console class tlaup builds; a closed pipe is an error for the handler, not an exit here."""

    def on_broken_pipe(self) -> None:
        raise BrokenPipeError  # Rich's own version points stdout at the null device and exits 1 (F10)


def _is_terminal(stream: TextIO) -> bool:
    try:
        return bool(stream.isatty())
    except (AttributeError, ValueError, OSError):
        return False


def _make_console(
    stream: TextIO,
    *,
    color: ColorPolicy,
    env: Mapping[str, str],
    terminal: bool | None,
    size: tuple[int, int] | None,
) -> Console:
    """Build one console from what `Ui` decided; Rich's own reading of `os.environ` decides nothing it is given."""
    is_terminal = _is_terminal(stream) if terminal is None else terminal
    colored = (is_terminal and not env.get("NO_COLOR")) if color is None else color
    if color is True:
        force_terminal: bool | None = True
    elif terminal is None and is_terminal:
        force_terminal = None  # a real terminal: let Rich look at it (TERM=dumb included)
    else:
        force_terminal = is_terminal
    # Rich's "standard" is the 16 ANSI colours; "auto" lets a real terminal show more but honours TERM=dumb.
    color_system = ("standard" if color is True or terminal is not None else "auto") if colored else None
    return _PipeConsole(
        file=stream,
        force_terminal=force_terminal,
        color_system=color_system,  # type: ignore[arg-type]
        no_color=not colored,
        markup=False,
        emoji=False,
        highlight=False,
        width=size[0] if size else None,
        height=size[1] if size else None,
    )


class Ui:
    """Messages and the one prompt, on streams that are passed in (design 14 F6).

    Format, all on stderr: `error: ...`, `hint: ...`, `warning: ...`, and `note` with no prefix; `result` goes to
    stdout. Only the prefix is coloured. Text from outside is never markup.
    """

    def __init__(  # noqa: PLR0913 - the signature is the design's (F6)
        self,
        stdout: TextIO,
        stderr: TextIO,
        stdin: TextIO,
        *,
        color: ColorPolicy,
        env: Mapping[str, str],
        interactive: bool | None = None,
        terminal: bool | None = None,
        size: tuple[int, int] | None = None,
    ) -> None:
        self._stdin = stdin
        self._stderr = stderr
        self._interactive = interactive
        self.out: Console = _make_console(stdout, color=color, env=env, terminal=terminal, size=size)
        self.err: Console = _make_console(stderr, color=color, env=env, terminal=terminal, size=size)

    @classmethod
    def for_process(cls) -> "Ui":
        """The process's own three streams and environment; needs no settings and raises nothing."""
        for stream in (sys.stdout, sys.stderr):
            reconfigure = getattr(stream, "reconfigure", None)
            if reconfigure is not None:  # not under CliRunner, whose streams are not TextIOWrappers
                with contextlib.suppress(ValueError, OSError):
                    reconfigure(errors="replace")
        return cls(sys.stdout, sys.stderr, sys.stdin, color=None, env=dict(os.environ))

    def _line(self, prefix: str, style: str, message: str) -> None:
        self.err.print(Text.assemble((prefix, style), " ", message), soft_wrap=True)

    def error(self, message: str, *, hint: str | None = None, details: str | None = None) -> None:
        self._line("error:", "red", message)
        if hint is not None:
            self._line("hint:", "cyan", hint)
        if details:
            for line in details.splitlines():
                self.err.print(Text("  " + line), soft_wrap=True)

    def warning(self, message: str) -> None:
        self._line("warning:", "yellow", message)

    def note(self, message: str) -> None:
        self.err.print(Text(message), soft_wrap=True)

    def result(self, renderable: Any) -> None:
        if isinstance(renderable, str):
            self.out.print(Text(renderable), soft_wrap=True)
        else:
            self.out.print(renderable)

    def ask(self, question: str, *, choices: Sequence[str], default: str | None) -> str:
        """Ask on stderr, read one line from the stream given; end of input is `CannotAsk`.

        An answer is compared with the choices exactly, after stripping white space. A line with nothing in it gives
        the default (asked again when there is none); any other answer is asked again.
        """
        shown = "/".join(choices)
        suffix = f" [{shown}]" + (f" (default: {default})" if default is not None else "")
        while True:
            self.err.print(Text(f"{question}{suffix}: "), end="", soft_wrap=True)
            self._stderr.flush()
            line = self._stdin.readline()
            if line == "":
                raise CannotAsk(_INPUT_ENDED)
            answer = line.strip()
            if answer == "" and default is not None:
                return default
            if answer in choices:
                return answer

    def is_interactive(self) -> bool:
        """The `interactive` argument when given; else stdin and stderr are both terminals."""
        if self._interactive is not None:
            return self._interactive
        return _is_terminal(self._stdin) and _is_terminal(self._stderr)
