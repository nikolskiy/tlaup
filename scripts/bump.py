"""Move the project version in pyproject.toml and uv.lock together (design 30 L4).

    uv run poe bump patch|minor|major

Runs ``uv version --bump <part>``, which updates ``uv.lock`` too, then prints the new version and
the next step of the release guide. It does not edit the changelog and does not commit.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PARTS = ("patch", "minor", "major")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1 or args[0] not in PARTS:
        sys.stderr.write(f"usage: poe bump {'|'.join(PARTS)} (give exactly one of {', '.join(PARTS)})\n")
        return 2
    uv = shutil.which("uv")
    if uv is None:
        sys.stderr.write("uv is not on PATH; install it to bump the version.\n")
        return 1
    result = subprocess.run(
        [uv, "version", "--bump", args[0], "--short"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.stderr.write(f"uv version --bump {args[0]} failed (exit {result.returncode}); nothing else was done.\n")
        return 1
    version = result.stdout.strip()
    sys.stdout.write(f"Version is now {version} in pyproject.toml and uv.lock.\n")
    sys.stdout.write(f"Next: rename ## [Unreleased] in CHANGELOG.md to ## [{version}] - <today>.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
