#!/usr/bin/env python3
"""Turn a checkout of main into the release commit's tree (design 30 L8).

    scripts/prepare_release.py patch|minor|major [--date YYYY-MM-DD]

Refuses when ``## [Unreleased]`` in CHANGELOG.md has no entries, before changing anything. Then it
runs ``uv version --bump <part>``, which moves pyproject.toml and uv.lock together (L4), and
renames ``## [Unreleased]`` to ``## [X.Y.Z] - <date>`` with an empty ``## [Unreleased]`` above it.
The date is today in UTC unless given. Prints the new version alone on stdout; messages go to
stderr. Run by ``scripts/release.py``; it does not commit.
"""

from __future__ import annotations

import datetime
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

REPO_ROOT = Path(__file__).resolve().parent.parent
PARTS = ("patch", "minor", "major")
_UNRELEASED = "## [Unreleased]"
_HEADING = re.compile(r"## \[")


class PrepareError(Exception):
    """The release cannot be prepared; the message says why."""


def _changelog_section() -> ModuleType:
    """scripts/changelog_section.py, loaded by path so that this works however it is started."""
    path = Path(__file__).resolve().parent / "changelog_section.py"
    spec = importlib.util.spec_from_file_location("changelog_section", path)
    if spec is None or spec.loader is None:  # pragma: no cover - the file is in the repository
        message = f"cannot load {path}"
        raise PrepareError(message)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def unreleased_entries(text: str) -> str:
    """The body under ``## [Unreleased]``, up to the next ``## [`` heading; PrepareError if none."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.rstrip() == _UNRELEASED]
    if len(starts) != 1:
        found = "no" if not starts else f"{len(starts)}"
        message = f"CHANGELOG.md has {found} {_UNRELEASED} headings; it needs exactly one."
        raise PrepareError(message)
    body: list[str] = []
    for line in lines[starts[0] + 1 :]:
        if _HEADING.match(line):
            break
        body.append(line)
    entries = "\n".join(body).strip()
    if not entries:
        message = f"{_UNRELEASED} in CHANGELOG.md has no entries, so there is nothing to release."
        raise PrepareError(message)
    return entries


def date_changelog(text: str, version: str, date: datetime.date) -> str:
    """``text`` with Unreleased's entries moved under ``## [version] - date``, Unreleased left empty."""
    unreleased_entries(text)
    dated = f"{_UNRELEASED}\n\n## [{version}] - {date.isoformat()}"
    lines = text.split("\n")
    index = next(i for i, line in enumerate(lines) if line.rstrip() == _UNRELEASED)
    lines[index] = dated
    result = "\n".join(lines)
    module = _changelog_section()
    try:
        module.section(result, version)
    except module.ChangelogError as error:
        message = f"CHANGELOG.md would not be releasable as {version}: {error}"
        raise PrepareError(message) from error
    return result


def bump(part: str) -> str:
    """Run ``uv version --bump part`` in the repository and return the new version."""
    uv = shutil.which("uv")
    if uv is None:
        message = "uv is not on PATH; it is needed to bump the version."
        raise PrepareError(message)
    result = subprocess.run(
        [uv, "version", "--bump", part, "--no-sync", "--short"],
        cwd=REPO_ROOT,
        stdout=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = f"uv version --bump {part} failed (exit {result.returncode})."
        raise PrepareError(message)
    return result.stdout.strip()


def main(
    argv: list[str] | None = None, changelog: Path | None = None, bumper: Callable[[str], str] | None = None
) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = REPO_ROOT / "CHANGELOG.md" if changelog is None else changelog
    run_bump = bump if bumper is None else bumper
    date = datetime.datetime.now(tz=datetime.UTC).date()
    if len(args) == 3 and args[1] == "--date":
        try:
            date = datetime.date.fromisoformat(args[2])
        except ValueError:
            sys.stderr.write(f"--date {args[2]} is not a date of the form YYYY-MM-DD.\n")
            return 2
        args = args[:1]
    if len(args) != 1 or args[0] not in PARTS:
        sys.stderr.write(f"usage: scripts/prepare_release.py {'|'.join(PARTS)} [--date YYYY-MM-DD]\n")
        return 2
    try:
        text = path.read_text(encoding="utf-8")
        unreleased_entries(text)  # refuse before the bump changes anything
        version = run_bump(args[0])
        path.write_text(date_changelog(text, version, date), encoding="utf-8")
    except PrepareError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    except OSError as error:
        sys.stderr.write(f"Cannot read or write {path}: {error.strerror}.\n")
        return 1
    sys.stderr.write(f"Version {version}: pyproject.toml, uv.lock and CHANGELOG.md are ready.\n")
    sys.stdout.write(f"{version}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
