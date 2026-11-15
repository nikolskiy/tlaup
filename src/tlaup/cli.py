"""TLA+ CLI tool - entry point."""

import importlib.metadata

import typer

from tlaup.cmd.check_java import check_java
from tlaup.cmd.config import app as config_app
from tlaup.cmd.fetch_cache import app as fetch_cache_app
from tlaup.cmd.modules import app as modules_app
from tlaup.cmd.tlc import tlc as run_tlc_cmd
from tlaup.cmd.tools import app as tools_app
from tlaup.config.loader import load_config
from tlaup.versioning import get_app_version

app = typer.Typer(
    name="tlaup",
    help="TLA+ tools: download TLA+ toolset distribution, compile custom modules, run model checker.",
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool) -> None:
    if value:
        meta = importlib.metadata.metadata("tlaup")
        app_ver = get_app_version(base_version=meta["Version"])
        typer.echo(f"{meta['Name']} v{app_ver}")
        typer.echo(meta["Summary"])
        raise typer.Exit()


@app.callback()
def root(
    _: bool = typer.Option(
        None,
        "--version",
        "-v",
        help="Show the application's version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """TLA+ CLI tool."""
    # Load config early to trigger first-run copy
    load_config()


# --- Subcommands ---

app.add_typer(modules_app, name="modules")
app.add_typer(tools_app, name="tools")
app.add_typer(fetch_cache_app, name="fetch-cache")
app.add_typer(config_app, name="config")

app.command(name="tlc")(run_tlc_cmd)
app.command(name="check-java")(check_java)


def main() -> None:
    """Entry point for [project.scripts]."""
    app()
