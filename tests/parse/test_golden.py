"""Properties every TLC golden file and every synthetic file keeps through ``TlcParser`` (design 01 T3, 10 P3, P4).

Each file is driven as the runner drives it (``tests/parse/drive.py``): read in binary, split into lines that keep
their newline, decoded as UTF-8 with ``errors="replace"``, fed one line per call, then ``close()``. Package 13 adds
the per-file properties; package 15 adds the comparison with the expected JSON.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING

import pytest

from tests.parse.drive import build_folders, golden_root, read_lines
from tlaup_parse import Framer, OutputLine, RunResult, TlcMessage, TlcParser, Unframed

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
