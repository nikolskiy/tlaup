"""How a golden file is read and fed to the parser, exactly as the runner does it (design 01 T3, package 08).

Shared by ``test_facts.py`` and the later golden tests (packages 13 and 15). ``tlaup_parse`` is imported only
inside ``parse_tlc``, so that collecting the tests that use this module works while the parser does not exist.
"""

from __future__ import annotations

import importlib
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tlaup_parse import RunResult

TOOLS = ("tlc", "sany", "pcal")


def golden_root() -> Path:
    """``tests/parse/golden``, found from this file: the isolation fixture changes the working folder (01 T2)."""
    return Path(__file__).resolve().parent / "golden"


def build_folders(tool: str) -> list[Path]:
    """The build folders of ``tlc/``, ``sany/`` or ``pcal/`` that have a ``build.toml``, sorted by name."""
    if tool not in TOOLS:
        msg = f"unknown tool folder {tool!r}; expected one of {TOOLS}"
        raise ValueError(msg)
    return sorted(folder for folder in (golden_root() / tool).iterdir() if (folder / "build.toml").is_file())


def _toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def line_of(folder: Path) -> str:
    """The release line of a build folder, ``stable`` or ``rolling``: ``build.toml``'s ``line``."""
    return str(_toml(folder / "build.toml")["line"])


def cases_of(folder: Path) -> dict[str, dict[str, object]]:
    """The case tables of a build folder's ``cases.toml``, by case name; the ``plain`` cases are left out."""
    data = _toml(folder / "cases.toml")
    return {name: table for name, table in data.items() if name != "plain" and isinstance(table, dict)}


def read_lines(path: Path) -> list[str]:
    """The file's lines as the launcher hands them on (design 20 G3).

    Read in binary, split on ``\\n`` with each line keeping its ending, and each line decoded as UTF-8 with
    ``errors="replace"``. A last line without an ending is kept as it is.
    """
    parts = path.read_bytes().split(b"\n")
    raw = [part + b"\n" for part in parts[:-1]]
    if parts[-1]:
        raw.append(parts[-1])
    return [line.decode("utf-8", errors="replace") for line in raw]


def parse_tlc(path: Path) -> RunResult:
    """A new ``TlcParser``, fed the file one line per call, closed; its ``result``."""
    parse = importlib.import_module("tlaup_parse")
    parser = parse.TlcParser()
    for line in read_lines(path):
        parser.feed(line)
    parser.close()
    result: RunResult = parser.result
    return result
