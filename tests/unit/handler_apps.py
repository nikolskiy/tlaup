"""Small apps that the real-process tests run through `run_app` (design 14 F10).

Started as `python handler_apps.py <case> [arguments]`: the case is a command of the small app, built with
`cls=TlaupGroup`, so tlaup gains no hidden command. `twice` runs `run_app` two times in one process.
"""

import contextlib
import sys

import typer

from tlaup.cli import TlaupGroup, run_app
from tlaup.errors import ConfigInvalid
from tlaup.ui import Ui

app = typer.Typer(
    cls=TlaupGroup, name="small", add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False
)


@app.callback()
def root(debug: bool = typer.Option(False, "--debug")) -> None:
    """A root with tlaup's --debug."""


@app.command("domain-error")
def domain_error() -> None:
    raise ConfigInvalid("the config is broken", hint="run tlaup config edit")  # noqa: TRY003


@app.command("internal-error")
def internal_error() -> None:
    raise RuntimeError("boom")


@app.command("lines")
def print_lines(count: int) -> None:
    ui = Ui.for_process()
    for number in range(count):
        ui.result(f"line {number}")


@app.command("forever")
def forever() -> None:
    ui = Ui.for_process()
    number = 0
    while True:
        ui.result(f"line {number} " + "x" * 60)
        number += 1


@app.command("exit")
def exit_with(code: int) -> None:
    raise typer.Exit(code)


def main(argv: list[str]) -> None:
    if argv[1:2] == ["twice"]:
        sys.argv = [argv[0], "exit", "1"]
        with contextlib.suppress(SystemExit):
            run_app(app)
        sys.argv = [argv[0], "--help"]
    run_app(app)


if __name__ == "__main__":
    main(sys.argv)
