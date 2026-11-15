import typer

from tlaup.cmd.config import app
from tlaup.config.loader import config_path


@app.command(name="list")
def list_config() -> None:
    """Display the current configuration file content."""
    cp = config_path()
    if not cp.exists():
        typer.echo("Configuration file not found.", err=True)
        raise typer.Exit(1)

    with cp.open(encoding="utf-8") as f:
        typer.echo(f.read())
