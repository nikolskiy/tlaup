import shutil
from pathlib import Path

import requests
from rich.progress import BarColumn, DownloadColumn, Progress, TransferSpeedColumn

from tlaup.versioning.metadata import write_version_metadata
from tlaup.versioning.paths import get_tools_dir
from tlaup.versioning.schema import RemoteVersion


def _download_jar(url: str, jar_path: Path, label: str) -> None:
    """Download a jar file from *url* with a progress bar."""
    response = requests.get(
        url,
        stream=True,
        timeout=30,
        headers={"User-Agent": "tlaup"},
    )
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))

    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
    ) as progress:
        task = progress.add_task(f"Downloading {label}...", total=total or None)
        with jar_path.open("wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(task, advance=len(chunk))


def download_version(
    target: RemoteVersion, *, force: bool = False, base_dir: Path | None = None, jar_name: str = "tla2tools.jar"
) -> Path:
    """Download a version jar. Returns the version directory path."""
    if base_dir is None:
        base_dir = get_tools_dir()
    version_dir = base_dir / f"{target.name}-{target.short_sha}"

    if version_dir.exists() and not force:
        return version_dir

    if version_dir.exists():
        shutil.rmtree(version_dir)

    version_dir.mkdir(parents=True, exist_ok=True)
    jar_path = version_dir / jar_name

    try:
        _download_jar(target.jar_download_url, jar_path, target.name)
    except (requests.RequestException, OSError):
        shutil.rmtree(version_dir, ignore_errors=True)
        raise

    write_version_metadata(version_dir, target)

    return version_dir
