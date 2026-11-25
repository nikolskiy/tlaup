"""The golden files are consistent with their ``cases.toml`` and ``build.toml`` (design 01 T3, package 07).

These tests read files only; they import nothing from ``tlaup`` or ``tlaup_parse``.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

GOLDEN = Path(__file__).resolve().parent / "golden"
SPECS = GOLDEN / "specs"
SYNTHETIC = GOLDEN / "synthetic"
TOOLS = ("tlc", "sany", "pcal")
FOLDERS = sorted(folder for tool in TOOLS for folder in (GOLDEN / tool).iterdir() if folder.is_dir())
FOLDER_IDS = [f"{folder.parent.name}/{folder.name}" for folder in FOLDERS]
EXIT_LINE = re.compile(rb"^\[exit=\d+\]$|\[rc=\d+\]$")


def load(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def tables(folder: Path) -> dict[str, dict[str, Any]]:
    """Every case table of a folder, keyed by its file's path relative to the folder, without the extension."""
    data = load(folder / "cases.toml")
    plain = data.pop("plain", {})
    found = dict(data)
    found |= {f"plain/{name}": table for name, table in plain.items()}
    return found


@pytest.mark.parametrize("tool", TOOLS)
def test_each_tool_has_one_stable_and_one_rolling_folder(tool: str) -> None:
    lines = [load(folder / "build.toml")["line"] for folder in FOLDERS if folder.parent.name == tool]
    assert sorted(lines) == ["rolling", "stable"]


@pytest.mark.parametrize("folder", FOLDERS, ids=FOLDER_IDS)
def test_every_capture_has_one_table_and_every_table_its_capture(folder: Path) -> None:
    outs = {p.relative_to(folder).with_suffix("").as_posix() for p in folder.rglob("*.out")}
    cases = tables(folder)
    assert outs == set(cases)
    for name, table in cases.items():
        assert table.get("plain", False) == name.startswith("plain/"), name
        if "stderr" in table:
            assert (folder / name).parent.joinpath(table["stderr"]).is_file(), name
    errs = {p.relative_to(folder).as_posix() for p in folder.rglob("*.err")}
    named = {(Path(name).parent / table["stderr"]).as_posix() for name, table in cases.items() if "stderr" in table}
    assert errs == named


@pytest.mark.parametrize("folder", FOLDERS, ids=FOLDER_IDS)
def test_every_spec_names_a_file_under_the_golden_specs(folder: Path) -> None:
    missing = [
        (name, table["spec"])
        for name, table in tables(folder).items()
        if "spec" in table and not (SPECS / (table["spec"] + ".tla")).is_file()
    ]
    assert missing == []


def test_every_synthetic_case_has_its_note() -> None:
    outs = {p.stem for p in SYNTHETIC.glob("*.out")}
    whys = {p.stem for p in SYNTHETIC.glob("*.why")}
    assert outs == whys
    assert len(outs) == 15


def test_the_byte_level_synthetic_cases_are_unchanged() -> None:
    crlf = (SYNTHETIC / "crlf.out").read_bytes()
    lines = crlf.split(b"\n")
    assert lines[-1] == b""
    assert all(line.endswith(b"\r") for line in lines[:-1])
    invalid = (SYNTHETIC / "invalid-utf8.out").read_bytes()
    assert b"\xff\xfe" in invalid
    assert b"\xe9" in invalid


@pytest.mark.parametrize("folder", FOLDERS, ids=FOLDER_IDS)
def test_no_capture_holds_research_12s_framing_lines(folder: Path) -> None:
    framed = []
    for out in folder.rglob("*.out"):
        lines = out.read_bytes().splitlines()
        if (lines and lines[0].startswith(b"$ ")) or any(EXIT_LINE.search(line) for line in lines):
            framed.append(out.relative_to(folder).as_posix())
    assert framed == []
