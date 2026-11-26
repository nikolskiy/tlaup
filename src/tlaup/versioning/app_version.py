"""App version discovery and git commit resolution for development installations (design 14 F9)."""

import importlib.metadata
import json
import shutil
import subprocess
from pathlib import Path

GIT_TIMEOUT = 2  # seconds: a `--version` never waits longer than this for git


def is_editable_install(dist: importlib.metadata.Distribution | None = None) -> bool:
    """Whether the tlaup distribution is installed in editable / development mode (`direct_url.json`)."""
    try:
        if dist is None:
            dist = importlib.metadata.distribution("tlaup")
        raw = dist.read_text("direct_url.json")
        if raw:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get("dir_info", {}).get("editable") is True:
                return True
    except (importlib.metadata.PackageNotFoundError, ValueError, TypeError, KeyError, AttributeError):
        pass
    return False


def get_git_commit_hash(base_dir: Path | None = None) -> str | None:
    """The short commit hash from `git rev-parse --short HEAD`, or None when git cannot say within two seconds."""
    git = shutil.which("git")
    if git is None:
        return None
    cwd = base_dir if (base_dir and base_dir.is_dir()) else Path(__file__).parent
    try:
        res = subprocess.run(
            [git, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=cwd,
            timeout=GIT_TIMEOUT,
        )
    except (subprocess.SubprocessError, OSError):  # TimeoutExpired is a SubprocessError
        return None
    if res.returncode != 0:
        return None
    commit = res.stdout.strip()
    return commit if len(commit) >= 7 else None


def get_app_version(base_version: str | None = None, *, editable: bool | None = None) -> str:
    """The version string; `+<short commit>` is added only for an editable install, and only when git answers.

    A normal install never starts git.
    """
    if not base_version:
        try:
            base_version = importlib.metadata.metadata("tlaup")["Version"]
        except (importlib.metadata.PackageNotFoundError, KeyError):
            base_version = "0.0.0"
    if editable is None:
        editable = is_editable_install()
    if editable:
        git_hash = get_git_commit_hash()
        if git_hash:
            return f"{base_version}+{git_hash}"
    return base_version
