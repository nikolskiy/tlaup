"""The `tool` group (design 23 C1, decision D47): its Typer object; `cli.py` registers its commands."""

import typer

app = typer.Typer(name="tool", help="Install, pin and remove TLA+ tools builds (tla2tools.jar).", no_args_is_help=True)
