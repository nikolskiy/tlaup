"""Properties every TLC golden file and every synthetic file keeps through ``TlcParser`` (design 01 T3, 10 P3, P4).

Each file is driven as the runner drives it (``tests/parse/drive.py``): read in binary, split into lines that keep
their newline, decoded as UTF-8 with ``errors="replace"``, fed one line per call, then ``close()``. Package 13 adds
the per-file properties; package 15 adds the comparison of every parsed case, of TLC, SANY and PlusCal, with its
expected ``<case>.json`` beside its ``.out`` (design 01 T3, T8).
"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING

import pytest

from tests.expected import assert_matches
from tests.parse.drive import build_folders, golden_root, read_lines
from tlaup_parse import Framer, OutputLine, PcalParser, RunResult, SanyParser, TlcMessage, TlcParser, Unframed

if TYPE_CHECKING:
    from pathlib import Path

    from tlaup_parse import Event

FILES = [path for folder in build_folders("tlc") for path in sorted(folder.glob("*.out"))] + sorted(
    (golden_root() / "synthetic").glob("*.out")
)
IDS = [f"{path.parent.name}/{path.stem}" for path in FILES]


def _drive(lines: list[str]) -> tuple[RunResult, list[Event]]:
    parser = TlcParser()
    events: list[Event] = []
    for line in lines:
        events.extend(parser.feed(line))
    events.extend(parser.close())
    return parser.result, events


def _without_ending(line: str) -> str:
    """The line as the framer reads it: one trailing ``\\r\\n`` or ``\\n`` removed."""
    if line.endswith("\r\n"):
        return line[:-2]
    return line.removesuffix("\n")


def _framed(lines: list[str]) -> list[Unframed | TlcMessage]:
    framer = Framer()
    items: list[Unframed | TlcMessage] = []
    for line in lines:
        items.extend(framer.feed(line))
    items.extend(framer.close())
    return items


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_nothing_is_lost_at_the_event_level(path: Path) -> None:
    lines = read_lines(path)
    result, events = _drive(lines)
    outputs = sum(isinstance(event, OutputLine) for event in events)
    assert outputs == result.unframed_lines - result.sany_lines_used
    items = _framed(lines)
    messages = [item for item in items if isinstance(item, TlcMessage)]
    second_count = sum(isinstance(item, Unframed) for item in items) + sum(
        bool(m.before) + bool(m.after) for m in messages
    )
    assert result.unframed_lines == second_count
    # Each message is carried at least as many times as it was framed: equal messages are counted, not matched once.
    carried = Counter(m for event in events if (m := getattr(event, "message", None)) is not None)
    framed = Counter(messages)
    lost = [m.code for m, n in framed.items() if carried[m] < n]
    assert lost == []


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_line_endings_do_not_matter(path: Path) -> None:
    bare = [_without_ending(line) for line in read_lines(path)]
    with_lf, events_lf = _drive([line + "\n" for line in bare])
    without, events_without = _drive(bare)
    with_crlf, events_crlf = _drive([line + "\r\n" for line in bare])
    assert without.to_dict() == with_lf.to_dict()
    assert with_crlf.to_dict() == with_lf.to_dict()
    assert events_without == events_lf
    assert events_crlf == events_lf


@pytest.mark.parametrize("path", FILES, ids=IDS)
def test_the_dictionary_form_holds(path: Path) -> None:
    result, _ = _drive(read_lines(path))
    data = result.to_dict()
    assert json.loads(json.dumps(data)) == data
    assert RunResult.from_dict(data) == result


def _is_sany_synthetic(path: Path) -> bool:
    # A synthetic file named sany-* holds SANY's own output, not TLC's (package 12), so it takes the SANY shape
    # (lead's decision for 15a).
    return path.parent.name == "synthetic" and path.stem.startswith("sany-")


def _parsed_cases() -> list[tuple[str, str, Path]]:
    """Every parsed case as (tool, build, capture): the cases of ``tlc/``, ``sany/`` and ``pcal/`` (not
    ``plain/``, which is not parsed) and every file of ``synthetic/``."""
    cases = [
        (tool, folder.name, path)
        for tool in ("tlc", "sany", "pcal")
        for folder in build_folders(tool)
        for path in sorted(folder.glob("*.out"))
    ]
    cases += [("synthetic", "", path) for path in sorted((golden_root() / "synthetic").glob("*.out"))]
    return cases


CASES = _parsed_cases()


def _case_id(tool: str, build: str, path: Path) -> str:
    return f"{tool}/{build}/{path.stem}" if build else f"{tool}/{path.stem}"


def _expected_param(tool: str, build: str, path: Path) -> object:
    return pytest.param(tool, path, id=_case_id(tool, build, path))


def _sany_expected(lines: list[str]) -> dict[str, object]:
    parser = SanyParser()
    classified = []
    for line in lines:
        step = parser.feed(line)
        assert step.line_class is not None
        classified.append({"class": step.line_class.value, "text": _without_ending(line)})
    parser.close()
    return {"result": parser.result.to_dict(), "lines": classified}


def _pcal_expected(lines: list[str]) -> dict[str, object]:
    parser = PcalParser()
    for line in lines:
        parser.feed(line)
    parser.close()
    return parser.result.to_dict()


def _serialised(tool: str, path: Path) -> str:
    """The expected file's text for one case: TLC and synthetic ``RunResult.to_dict()``; SANY the result and each
    line's class; PlusCal ``PcalResult.to_dict()``. Keys in the order ``to_dict()`` gives them, not sorted."""
    lines = read_lines(path)
    if tool == "sany" or _is_sany_synthetic(path):
        data = _sany_expected(lines)
    elif tool == "pcal":
        data = _pcal_expected(lines)
    else:
        data = _drive(lines)[0].to_dict()
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


@pytest.mark.parametrize(("tool", "path"), [_expected_param(*case) for case in CASES])
def test_expected_result(tool: str, path: Path, request: pytest.FixtureRequest) -> None:
    assert_matches(_serialised(tool, path), path.with_suffix(".json"), request)


def test_every_expected_file_has_its_capture() -> None:
    # A .json beside no parsed case (a removed case, a plain/ capture) would never be compared: its test does not exist.
    captures = {path for _, _, path in CASES}
    left_behind = [path for path in sorted(golden_root().rglob("*.json")) if path.with_suffix(".out") not in captures]
    assert left_behind == []


def test_every_case_has_its_expected_file() -> None:
    missing = [_case_id(tool, build, path) for tool, build, path in CASES if not path.with_suffix(".json").is_file()]
    assert missing == []


def test_every_tool_has_cases() -> None:
    # The two checks above pass vacuously over an empty glob; every parsed tool and the synthetic folder name cases.
    assert {tool for tool, _, _ in CASES} == {"tlc", "sany", "pcal", "synthetic"}
