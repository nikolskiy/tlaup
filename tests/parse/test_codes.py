"""The code table ``tlaup_parse.codes.CODES`` (design 10 P4 and P5; preserved-behaviour row R29, its framing half)."""

from __future__ import annotations

import dataclasses
from collections import Counter
from typing import TYPE_CHECKING

import pytest

from tests.parse.drive import golden_root, read_lines
from tlaup_parse import ErrorKind, Framer, TlcMessage
from tlaup_parse.codes import CODES, CodeInfo

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

TLC_FILES = sorted((golden_root() / "tlc").rglob("*.out"))
TLC_FILE_IDS = [path.relative_to(golden_root()).as_posix() for path in TLC_FILES]

ADDED = {
    1003: "SYSTEM_OUT_OF_MEMORY_LIVENESS",
    2148: "TLC_STATE_NOT_COMPLETELY_SPECIFIED_LIVE",
    2254: "SYSTEM_FINGERPRINT_OVERFLOW_ERROR",
    2256: "TLC_NO_STATES_SATISFYING_INIT_AND_CONSTRAINT",
    2404: "TLC_POSTCONDITION_FALSE",
    2405: "TLC_POSTCONDITION_EVALUATION_ERROR",
    2285: "TLC_CHECKPOINT_RECOVER_SETTINGS_MISMATCH",
}

# P5's "Kind" bullet, as package 10 lists it.
KINDS = {
    2110: ErrorKind.INVARIANT,
    2114: ErrorKind.DEADLOCK,
    2116: ErrorKind.PROPERTY,
    2112: ErrorKind.PROPERTY,
    2132: ErrorKind.ASSERTION,
    2104: ErrorKind.ASSUMPTION,
    2179: ErrorKind.EVALUATION,
    2404: ErrorKind.POSTCONDITION,
    2405: ErrorKind.POSTCONDITION,
    5001: ErrorKind.CONFIG,
    5003: ErrorKind.CONFIG,
    5006: ErrorKind.CONFIG,
    2229: ErrorKind.CONFIG,
    1000: ErrorKind.EXCEPTION,
    1005: ErrorKind.EXCEPTION,
    2147: ErrorKind.EXCEPTION,
    2154: ErrorKind.EXCEPTION,
    2173: ErrorKind.EXCEPTION,
    3002: ErrorKind.PARSE,
    1102: ErrorKind.USAGE,
}


def framed_messages(path: Path) -> Iterator[TlcMessage]:
    """Every message framed from the file, top level and nested."""
    framer = Framer()
    items = [item for line in read_lines(path) for item in framer.feed(line)]
    items.extend(framer.close())
    stack = [item for item in items if isinstance(item, TlcMessage)]
    while stack:
        message = stack.pop()
        yield message
        stack.extend(message.nested)


@pytest.mark.parametrize("path", TLC_FILES, ids=TLC_FILE_IDS)
def test_every_framed_code_has_an_entry(path: Path) -> None:
    missing = sorted({message.code for message in framed_messages(path)} - CODES.keys())
    assert missing == []


def test_the_added_codes_have_their_upstream_names() -> None:
    assert {code: CODES[code].name for code in ADDED} == ADDED


def test_the_kinds_are_p5s_and_every_other_code_has_none() -> None:
    assert {code: info.kind for code, info in CODES.items() if info.kind is not None} == KINDS


def test_no_name_occurs_twice() -> None:
    twice = [name for name, count in Counter(info.name for info in CODES.values()).items() if count > 1]
    assert twice == []


def test_an_entry_holds_a_name_and_a_kind_and_no_class() -> None:
    assert [field.name for field in dataclasses.fields(CodeInfo)] == ["name", "kind"]
    assert all(isinstance(info, CodeInfo) for info in CODES.values())
