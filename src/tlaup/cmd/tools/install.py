from pathlib import Path

import requests
import typer

from tlaup.cmd.tools import app
from tlaup.config.loader import load_config
from tlaup.versioning import (
    download_version,
    fetch_remote_versions,
    get_pinned_version_dir,
    get_tools_dir,
    list_addresses,
    set_pin,
)


def _auto_pin_if_needed(version_dir: Path) -> None:
    """Pin the version if no version is currently pinned."""
    pinned_dir = get_pinned_version_dir()
    if pinned_dir is None:
        typer.echo(f"Auto-pinning newly installed version {version_dir.name}")
        set_pin(version_dir)


@app.command()
def install(
    version: str = typer.Argument(None, help="Version tag (e.g. 'v1.8.0')."),
    force: bool = typer.Option(False, "--force", "-f", help="Re-download if already installed."),
) -> None:
    """Download and install a specific TLC version."""
    config = load_config()
    versions, status = fetch_remote_versions(*list_addresses(config.tool.repository))

    if not versions:
        typer.echo(f"Error: Could not fetch remote versions (status: {status.value})", err=True)
        raise typer.Exit(1)

    target = None
    if version:
        target = next((v for v in versions if v.name == version), None)
        if not target:
            typer.echo(f"Error: Version {version} not found.", err=True)
            raise typer.Exit(1)
    else:
        typer.echo("No version specified, selecting latest stable release.")
        # Default to latest non-prerelease
        target = next((v for v in versions if not v.prerelease), versions[0])

    # Check if already installed
    target_dir = get_tools_dir() / f"{target.name}-{target.short_sha}"
    if target_dir.exists() and not force:
        typer.echo(f"Version {target.name} is already installed.")
        typer.echo(f"Successfully installed {target.name} to {target_dir}")
        _auto_pin_if_needed(target_dir)
        return

    try:
        version_dir = download_version(target, force=force)
        typer.echo("Download complete.")
        typer.echo(f"Successfully installed {target.name} to {version_dir}")
    except (requests.RequestException, OSError) as e:
        typer.echo(f"Error: Failed to download: {e}", err=True)
        raise typer.Exit(1) from e

    _auto_pin_if_needed(version_dir)
