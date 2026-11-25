import os
from datetime import UTC, datetime
from pathlib import Path

from tlaup.paths import AppPaths
from tlaup.versioning.store import ToolStore


def get_tlc_jar_path() -> Path | None:
    """The pinned build's tla2tools.jar in the new store, or None when nothing is pinned (until package 39)."""
    build = ToolStore(AppPaths.from_env(os.environ), now=lambda: datetime.now(UTC)).pinned()
    return build.jar if build is not None else None  # PinnedBuildMissing passes up to the handler (3)
