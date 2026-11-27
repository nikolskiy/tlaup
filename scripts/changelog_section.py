#!/usr/bin/env python3
"""Print one version's section of CHANGELOG.md (design 30 L1, L2, L3).

    scripts/changelog_section.py X.Y.Z

Prints the body under the heading ``## [X.Y.Z] - YYYY-MM-DD`` of the repository's ``CHANGELOG.md``
to stdout, without the heading, and exits 0. Fails with a message on stderr and exit 1 when the
heading is missing or malformed, when the section is empty, or when ``## [Unreleased]`` still has
entries. An ``## [Unreleased]`` heading with nothing under it is allowed.

Used by ``scripts/release.sh`` before tagging, by the release workflow for the release page's text,
and by hand to backfill old release pages. Standard library only.
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

CHANGELOG = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

_VERSION = re.compile(r"\d+\.\d+\.\d+")
_HEADING = re.compile(r"## \[(?P<name>[^\]]*)\](?P<rest>.*)")
_DATED = re.compile(r" - (?P<date>\d{4}-\d{2}-\d{2})")
_VERSION_LIKE = re.compile(r"v?\d+(?:\.\d+)*")


class ChangelogError(Exception):
    """The changelog does not hold a releasable section for the version."""


def _sections(text: str) -> list[tuple[str, str, list[str]]]:
    """Each ``## [`` heading as (name, text after the bracket, body lines up to the next one)."""
    sections: list[tuple[str, str, list[str]]] = []
    for line in text.splitlines():
        match = _HEADING.fullmatch(line.rstrip())
        if match:
            sections.append((match["name"], match["rest"], []))
        elif sections:
            sections[-1][2].append(line)
    return sections


def _numbers(name: str) -> tuple[int, ...]:
    parts = [int(p) for p in name.removeprefix("v").split(".")]
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _body(lines: list[str]) -> str:
    return "\n".join(lines).strip("\n")


def section(text: str, version: str) -> str:
    """The body of ``version``'s section in ``text``, or ChangelogError saying what is wrong."""
    if not _VERSION.fullmatch(version):
        message = f"{version!r} is not a version of the form X.Y.Z."
        raise ChangelogError(message)
    sections = _sections(text)

    for name, _rest, lines in sections:
        if name == "Unreleased" and _body(lines).strip():
            message = (
                f"## [Unreleased] still has entries. Rename it to ## [{version}] - YYYY-MM-DD,"
                " or move its entries into that section."
            )
            raise ChangelogError(message)

    found = [(rest, lines) for name, rest, lines in sections if name == version]
    if not found:
        for name, rest, _lines in sections:
            if _VERSION_LIKE.fullmatch(name) and _numbers(name) == _numbers(version):
                message = (
                    f"The heading ## [{name}]{rest} names {version} in another form."
                    f" Write it as ## [{version}] - YYYY-MM-DD."
                )
                raise ChangelogError(message)
        message = f"No heading ## [{version}] - YYYY-MM-DD in the changelog."
        raise ChangelogError(message)
    if len(found) > 1:
        message = f"The heading ## [{version}] appears {len(found)} times; keep one."
        raise ChangelogError(message)

    rest, lines = found[0]
    dated = _DATED.fullmatch(rest.rstrip())
    if dated is None:
        message = f"The heading ## [{version}]{rest} is malformed. Write it as ## [{version}] - YYYY-MM-DD."
        raise ChangelogError(message)
    try:
        datetime.date.fromisoformat(dated["date"])
    except ValueError:
        message = f"The heading ## [{version}]{rest} has {dated['date']}, which is not a valid date (YYYY-MM-DD)."
        raise ChangelogError(message) from None

    body = _body(lines)
    if not body.strip():
        message = f"The section ## [{version}] is empty. Add its entries."
        raise ChangelogError(message)
    return body + "\n"


def main(argv: list[str] | None = None, changelog: Path = CHANGELOG) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        sys.stderr.write("usage: scripts/changelog_section.py X.Y.Z\n")
        return 2
    try:
        text = changelog.read_text(encoding="utf-8")
    except OSError as e:
        sys.stderr.write(f"Cannot read {changelog}: {e.strerror}.\n")
        return 1
    try:
        body = section(text, args[0])
    except ChangelogError as e:
        sys.stderr.write(f"{changelog.name}: {e}\n")
        return 1
    sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
