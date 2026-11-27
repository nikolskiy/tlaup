"""Remove the build and coverage leftovers (design 30 H2): ``uv run poe clean``.

Removes ``dist/``, ``build/``, ``src/*.egg-info/``, ``.coverage``, ``.coverage.*``, ``htmlcov/`` and
``coverage.xml`` under the repository root, each only if present, and nothing else. It uses
``pathlib`` and ``shutil``, so it works from any folder and on Windows.
"""

from __future__ import annotations

import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def targets(root: Path) -> list[Path]:
    """The leftovers that exist under ``root``."""
    found = [root / name for name in ("dist", "build", "htmlcov", "coverage.xml", ".coverage")]
    found += sorted(root.glob(".coverage.*"))
    found += sorted((root / "src").glob("*.egg-info"))
    return [path for path in found if path.exists() or path.is_symlink()]


def main() -> int:
    for path in targets(REPO_ROOT):
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
