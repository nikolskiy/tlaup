import contextlib
from pathlib import Path

from tlaup.config.loader import cache_dir


def get_tools_dir() -> Path:
    return cache_dir() / "tools"


def get_modules_dir() -> Path:
    return cache_dir() / "modules"


def get_run_dir() -> Path:
    return cache_dir() / "run"


def get_tlc_run_dir() -> Path:
    return get_run_dir() / "tlc"


def get_pinned_path() -> Path:
    """Returns path to the pin marker file."""
    return get_tools_dir() / "tools-pinned-version.txt"


def get_pinned_version_dir() -> Path | None:
    """Returns the pinned version directory, or None if not pinned."""
    pin_file = get_pinned_path()
    if not pin_file.exists():
        return None
    dir_name = pin_file.read_text().strip()
    if not dir_name:
        return None
    target = get_tools_dir() / dir_name
    return target if target.is_dir() else None


def set_pin(version_dir: Path) -> None:
    """Pin a version by writing its directory name to tools-pinned-version.txt."""
    pin_file = get_pinned_path()
    pin_file.parent.mkdir(parents=True, exist_ok=True)
    pin_file.write_text(version_dir.name)


def clear_pin() -> None:
    """Remove the pin."""
    pin_file = get_pinned_path()
    if pin_file.exists():
        pin_file.unlink()


def clear_cache() -> None:
    """Remove all remote versions cache files."""
    cache_dir_path = cache_dir()
    for cache_file in cache_dir_path.glob("github_cache*.json"):
        with contextlib.suppress(OSError):
            cache_file.unlink()
