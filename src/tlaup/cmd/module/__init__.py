"""The `module` group (design 23 C1, decision D47): its Typer object; `cli.py` registers its commands."""

import typer

app = typer.Typer(
    name="module", help="Manage your own TLA+ modules, with optional Java operator overrides.", no_args_is_help=True
)
