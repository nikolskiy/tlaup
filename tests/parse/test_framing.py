"""Framing over the golden and synthetic files: the exact rebuild and the shapes of design 10 P4 (01 T3).

Every file is read as the launcher hands it on (``drive.read_lines``) and fed one line per call to a new
``Framer``. Nothing here types tool output (01 T12 rule 3): the lines come from the files.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.parse.drive import build_folders, golden_root, read_lines
from tlaup_parse import Framer, TlcMessage, Unframed, render_framed

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from pathlib import Path

GOLDEN = golden_root()
SYNTHETIC = GOLDEN / "synthetic"
FILES = sorted(path for tool in ("tlc", "sany", "pcal", "synthetic") for path in (GOLDEN / tool).rglob("*.out"))
FILE_IDS = [path.relative_to(GOLDEN).as_posix() for path in FILES]
TLC_BUILDS = build_folders("tlc")
TLC_BUILD_IDS = [folder.name for folder in TLC_BUILDS]

Item = Unframed | TlcMessage


def without_ending(line: str) -> str:
    """The line with a trailing ``\\r\\n`` or ``\\n`` removed, as P4 says the framer does."""
    if line.endswith("\r\n"):
        return line[:-2]
    return line.removesuffix("\n")


def frame(lines: Iterable[str]) -> list[Item]:
    """Everything a new ``Framer`` returns from ``feed`` and ``close``, in order."""
    framer = Framer()
    items: list[Item] = []
    for line in lines:
        items.extend(framer.feed(line))
    items.extend(framer.close())
    return items


def frame_file(path: Path) -> list[Item]:
    return frame(read_lines(path))


def messages(items: Iterable[Item]) -> list[TlcMessage]:
    return [item for item in items if isinstance(item, TlcMessage)]


def walk(message: TlcMessage) -> Iterator[TlcMessage]:
    """The message and every message nested in it, at any depth."""
    yield message
    for nested in message.nested:
        yield from walk(nested)


def only(items: Iterable[Item], code: int) -> TlcMessage:
    found = [message for message in messages(items) if message.code == code]
    assert len(found) == 1, f"top-level messages with code {code}: {len(found)}"
    return found[0]


@pytest.mark.parametrize("path", FILES, ids=FILE_IDS)
def test_rendering_what_the_framer_returned_rebuilds_the_file(path: Path) -> None:
    lines = read_lines(path)
    rendered = [out for item in frame(lines) for out in render_framed(item)]
    assert rendered == [without_ending(line) for line in lines]


@pytest.mark.parametrize("path", FILES, ids=FILE_IDS)
def test_line_endings_do_not_change_the_items(path: Path) -> None:
    bare = [without_ending(line) for line in read_lines(path)]
    as_lf = frame(line + "\n" for line in bare)
    assert frame(bare) == as_lf
    assert frame(line + "\r\n" for line in bare) == as_lf


@pytest.mark.parametrize("build", TLC_BUILDS, ids=TLC_BUILD_IDS)
def test_java_override_exception_nests_the_2154_after_four_lines(build: Path) -> None:
    error = only(frame_file(build / "java-override-exception.out"), 1000)
    assert [isinstance(item, str) for item in error.body] == [True, True, True, True, False]
    nested = error.body[4]
    assert isinstance(nested, TlcMessage)
    assert nested.code == 2154
    assert nested.before == ": "


@pytest.mark.parametrize("build", TLC_BUILDS, ids=TLC_BUILD_IDS)
def test_method_not_public_keeps_the_nested_2154_in_its_place(build: Path) -> None:
    items = frame_file(build / "override-method_not_public.out")
    outer = only(items, 2154)
    assert not outer.truncated
    assert [isinstance(item, str) for item in outer.body] == [True, False, True, True]
    nested = outer.body[1]
    assert isinstance(nested, TlcMessage)
    assert nested.code == 2154
    assert nested.after == ","
    following = messages(items[items.index(outer) + 1 :])
    assert following[0].code == 2186
    assert following[0].nested == ()


@pytest.mark.parametrize("build", TLC_BUILDS, ids=TLC_BUILD_IDS)
def test_ctor_private_is_a_1000_nested_in_a_1000(build: Path) -> None:
    outer = only(frame_file(build / "override-ctor_private.out"), 1000)
    assert [nested.code for nested in outer.nested] == [1000]


@pytest.mark.parametrize("build", TLC_BUILDS, ids=TLC_BUILD_IDS)
def test_print_marker_quoted_markers_are_unframed(build: Path) -> None:
    path = build / "print-marker.out"
    items = frame_file(path)
    quoted = [without_ending(line) for line in read_lines(path) if line.startswith('"')]
    assert quoted
    unframed = [item.line for item in items if isinstance(item, Unframed)]
    assert all(line in unframed for line in quoted)
    assert all(found.code != 9999 for message in messages(items) for found in walk(message))


TEXT_CASES = [
    ("v1.7.4", "java-override-exception"),
    ("v1.7.4", "java-override-stack-trace"),
    ("v1.7.4", "postcondition-false"),
    *[(folder.name, "java-override-exception") for folder in TLC_BUILDS if folder.name != "v1.7.4"],
    *[(folder.name, "java-override-stack-trace") for folder in TLC_BUILDS if folder.name != "v1.7.4"],
]


@pytest.mark.parametrize(("build", "case"), TEXT_CASES, ids=[f"{build}/{case}" for build, case in TEXT_CASES])
def test_text_lines_read_as_the_plain_capture(build: str, case: str) -> None:
    folder = GOLDEN / "tlc" / build
    errors = [m for m in messages(frame_file(folder / f"{case}.out")) if m.severity == 1 and m.nested]
    assert len(errors) == 1
    text = list(errors[0].text_lines())
    plain = [without_ending(line) for line in read_lines(folder / "plain" / f"{case}.out")]
    first = plain.index("Error: " + text[0])
    found = plain[first : first + len(text)]
    found[0] = found[0].removeprefix("Error: ")
    assert found == text


def test_startmsg_minus_one_is_plain_text() -> None:
    path = SYNTHETIC / "startmsg-minus-one.out"
    lines = [without_ending(line) for line in read_lines(path)]
    items = frame_file(path)
    assert items[1:4] == [Unframed(line) for line in lines[3:6]]
    assert [message.code for message in messages(items)] == [2262, 2186]


def test_a_leading_zero_is_plain_text() -> None:
    path = SYNTHETIC / "leading-zero.out"
    lines = [without_ending(line) for line in read_lines(path)]
    items = frame_file(path)
    assert items[1:4] == [Unframed(line) for line in lines[3:6]]
    start = items[4]
    assert isinstance(start, TlcMessage)
    assert start.code == 2185
    assert start.body == (lines[7], lines[8])
    assert [message.code for message in messages(items)] == [2262, 2185, 2186]


def test_a_start_with_no_end_is_closed_truncated() -> None:
    framer = Framer()
    returned = [item for line in read_lines(SYNTHETIC / "unterminated.out") for item in framer.feed(line)]
    assert [message.code for message in messages(returned)] == [2262]
    closed = framer.close()
    assert len(closed) == 1
    last = closed[0]
    assert isinstance(last, TlcMessage)
    assert last.code == 2185
    assert last.truncated
    assert len(last.body) == 1


def test_an_end_with_no_start_is_plain_text() -> None:
    path = SYNTHETIC / "end-without-start.out"
    lines = [without_ending(line) for line in read_lines(path)]
    items = frame_file(path)
    assert items[1] == Unframed(lines[3])
    start = only(items, 2185)
    assert lines[6] in start.body
    assert not start.truncated


def test_crossed_ends_close_the_inner_one_truncated() -> None:
    outer = only(frame_file(SYNTHETIC / "crossed-ends.out"), 1000)
    assert not outer.truncated
    assert [isinstance(item, str) for item in outer.body] == [True, False]
    inner = outer.body[1]
    assert isinstance(inner, TlcMessage)
    assert inner.code == 2154
    assert inner.truncated
    assert len(inner.body) == 1


def test_text_after_a_top_level_end_marker_is_the_messages_after() -> None:
    path = SYNTHETIC / "end-marker-text-after.out"
    lines = [without_ending(line) for line in read_lines(path)]
    start = only(frame_file(path), 2185)
    assert start.after
    assert lines[5].endswith(start.after)
    assert not start.truncated


def test_an_error_nested_in_information_is_one_top_level_message() -> None:
    outer = only(frame_file(SYNTHETIC / "error-in-info.out"), 2185)
    assert outer.severity == 0
    assert [(nested.code, nested.severity) for nested in outer.nested] == [(1000, 1)]


def test_crlf_frames_like_its_lf_twin() -> None:
    path = SYNTHETIC / "crlf.out"
    raw = path.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") > 0
    assert frame_file(path) == frame_file(GOLDEN / "tlc" / "v1.7.4" / "success.out")


def test_printed_end_marker_text_with_text_after_it_is_plain_text() -> None:
    path = SYNTHETIC / "print-end-marker.out"
    lines = [without_ending(line) for line in read_lines(path)]
    items = frame_file(path)
    assert Unframed(lines[6]) in items
    coverage = only(items, 2201)
    assert lines[9] in coverage.body
    assert [message.code for message in messages(items)] == [2262, 2185, 2201, 2186]


def test_invalid_utf8_frames_and_rebuilds() -> None:
    lines = read_lines(SYNTHETIC / "invalid-utf8.out")
    assert any("�" in line for line in lines)
    items = frame_file(SYNTHETIC / "invalid-utf8.out")
    assert [out for item in items for out in render_framed(item)] == [without_ending(line) for line in lines]
    assert messages(items)


def test_unknown_codes_keep_the_severities_of_their_markers() -> None:
    found = {message.code: message for message in messages(frame_file(SYNTHETIC / "unknown-code.out"))}
    assert {code: found[code].severity for code in (9901, 9902, 9903)} == {9901: 1, 9902: 3, 9903: 0}
    assert all(found[code].name is None for code in (9901, 9902, 9903))


def test_the_framer_names_a_known_code() -> None:
    version = frame_file(GOLDEN / "tlc" / "v1.7.4" / "success.out")[0]
    assert isinstance(version, TlcMessage)
    assert version.code == 2262
    assert version.name == "TLC_VERSION"
