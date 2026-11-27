"""Comparison against a stored expected file (design 01 T8)."""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

UPDATE_OPTION = "--update-expected"
WRITTEN = pytest.StashKey[list[Path]]()


def _normalise(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def written_files(config: pytest.Config) -> list[Path]:
    """The expected files this run wrote with ``--update-expected``, in the order written."""
    return config.stash.setdefault(WRITTEN, [])


def assert_matches(actual: str, expected: Path, request: pytest.FixtureRequest) -> None:
    """Compare ``actual`` with the file ``expected`` after normalising line endings.

    On a mismatch the test fails with a unified diff. With ``pytest --update-expected`` the
    file is written instead (with its folder if needed) and recorded, so that the end of the
    run lists it; a file that already matches is left alone.
    """
    config = request.config
    update = bool(config.getoption(UPDATE_OPTION))
    wanted = _normalise(actual)
    current = _normalise(expected.read_bytes().decode("utf-8")) if expected.exists() else None
    if current == wanted:
        return
    if update:
        expected.parent.mkdir(parents=True, exist_ok=True)
        expected.write_bytes(wanted.encode("utf-8"))
        written_files(config).append(expected)
        return
    if current is None:
        pytest.fail(f"expected file {expected} does not exist; run pytest with {UPDATE_OPTION} to write it")
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        wanted.splitlines(keepends=True),
        fromfile=str(expected),
        tofile="actual",
    )
    pytest.fail(f"output differs from {expected} (rewrite it with {UPDATE_OPTION}):\n" + "".join(diff))


def add_option(parser: pytest.Parser) -> None:
    parser.addoption(
        UPDATE_OPTION,
        action="store_true",
        default=False,
        help="write the expected files that differ instead of failing; review every file it lists",
    )


def report_written(terminalreporter: pytest.TerminalReporter, config: pytest.Config) -> None:
    written = written_files(config)
    if not written:
        return
    terminalreporter.section(f"expected files written by {UPDATE_OPTION}")
    for path in written:
        terminalreporter.write_line(str(path))
