from pathlib import Path

from tlaup.versioning import get_pinned_version_dir


def get_tlc_jar_path() -> Path | None:
    """Resolve the path to the pinned build's tla2tools.jar, or None when nothing usable is pinned."""
    pinned_dir = get_pinned_version_dir()
    pinned_jar = pinned_dir / "tla2tools.jar" if pinned_dir else None
    return pinned_jar if (pinned_jar and pinned_jar.exists()) else None
