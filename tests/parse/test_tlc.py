"""``TlcParser`` on synthetic files and on behaviour that is not a fact about one capture (design 10 P3, P4, P8;
package 13).

Every file is driven as the runner drives it (``tests/parse/drive.py``). The tests of trace states, and the event
orders that hold them, are package 13b's. ``test_unknown_codes_*`` is inventory row R29's test: the severity, not
the code, decides whether a message is an error or a warning.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.parse.drive import build_folders, golden_root, read_lines
from tlaup_parse import (
    CheckpointStarted,
    CheckpointWritten,
    DiagnosticFound,
    ErrorExtended,
    ErrorKind,
    ErrorOpened,
    Information,
    OutputLine,
    Phase,
    PhaseChanged,
    Recovered,
    RunResult,
    Status,
    TlcParser,
    UnknownMessage,
    Verdict,
)
from tlaup_parse.codes import CODES

if TYPE_CHECKING:
    from pathlib import Path

    from tlaup_parse import Event, TlcMessage

BUILDS = {folder.name: folder for folder in build_folders("tlc")}
SYNTHETIC = golden_root() / "synthetic"


def _drive(path: Path, parser: TlcParser | None = None) -> tuple[RunResult, list[Event]]:
    parser = parser or TlcParser()
    events: list[Event] = []
    for line in read_lines(path):
        events.extend(parser.feed(line))
    events.extend(parser.close())
    return parser.result, events


def _message(event: Event) -> TlcMessage | None:
    return getattr(event, "message", None)


def _outputs(events: list[Event]) -> list[str]:
    return [event.line for event in events if isinstance(event, OutputLine)]


# --- Synthetic cases (P3, P4) ---------------------------------------------------------------------------------------


def test_a_cut_off_run_is_running_and_incomplete() -> None:
    # cut-off.out is success.out cut inside its 2268, before the 2186 (cut-off.why).
    result, events = _drive(SYNTHETIC / "cut-off.out")
    assert result.status is Status.RUNNING
    assert result.verdict is Verdict.INCOMPLETE
    assert result.errors == []
    last = _message(events[-1])
    assert last is not None
    assert last.truncated
    assert last.code == 2268
    assert (result.finished, result.duration_ms) == (None, None)
    assert result.phase is not Phase.FINISHED


def test_a_severity_1_message_nested_in_a_severity_0_one_is_one_error() -> None:
    result, events = _drive(SYNTHETIC / "error-in-info.out")
    assert [(e.message.code, [m.code for m in e.message.nested]) for e in result.errors] == [(2185, [1000])]
    assert [type(e) for e in events if isinstance(e, ErrorOpened | ErrorExtended)] == [ErrorOpened]
    assert result.status is Status.FAILURE


def test_text_after_a_top_level_end_marker_is_an_output_line_after_the_message() -> None:
    path = SYNTHETIC / "end-marker-text-after.out"
    result, events = _drive(path)
    start = next(i for i, e in enumerate(events) if isinstance(e, PhaseChanged) and e.message.code == 2185)
    after = events[start + 1]
    assert isinstance(after, OutputLine)
    assert read_lines(path)[5].rstrip("\n").endswith(after.line)
    assert after.line
    assert result.output == [after.line]
    assert result.unframed_lines == 1  # no Unframed item, one top-level after text


@pytest.mark.parametrize("case", ["startmsg-minus-one", "leading-zero"])
def test_malformed_start_markers_are_output_lines(case: str) -> None:
    path = SYNTHETIC / f"{case}.out"
    result, events = _drive(path)
    plain = [line.rstrip("\n") for line in read_lines(path)[3:6]]  # lines 4 to 6 (the .why file)
    assert _outputs(events) == plain
    assert result.output == plain
    assert result.unknown_messages == []


def test_the_leading_zero_end_marker_stays_in_the_open_message() -> None:
    path = SYNTHETIC / "leading-zero.out"
    result, events = _drive(path)
    lines = read_lines(path)
    start = next(e for e in events if isinstance(e, PhaseChanged) and e.message.code == 2185)
    assert start.message.lines == (lines[7].rstrip("\n"), lines[8].rstrip("\n"))  # lines 8 and 9
    assert result.status is Status.SUCCESS


def test_invalid_utf8_parses_with_the_replacement_character_kept() -> None:
    # Line 17 of the file (bytes FF FE) is SANY's "Semantic processing" line inside the 2220 to 2219 window, so
    # the SANY parser uses it (class PROGRESS, design 10 P8) and it is no OutputLine; it is counted as used.
    path = SYNTHETIC / "invalid-utf8.out"
    lines = read_lines(path)
    assert "�" in lines[16]
    result, events = _drive(path)
    assert result.sany_lines_used == result.unframed_lines - len(_outputs(events))
    assert result.sany == []
    assert [e.message.code for e in result.errors] == [2110]


def test_unknown_codes_are_kept_and_their_severity_decides_the_class() -> None:
    # Inventory row R29. 9901 is severity 1, 9902 severity 3, 9903 severity 0 (unknown-code.why).
    result, events = _drive(SYNTHETIC / "unknown-code.out")
    unknown = [(type(e).__name__, m.code) for e in events if (m := _message(e)) is not None and m.code not in CODES]
    assert sorted(unknown, key=lambda pair: pair[1]) == [
        ("ErrorOpened", 9901),
        ("WarningFound", 9902),
        ("UnknownMessage", 9903),
    ]
    assert sorted(m.code for m in result.unknown_messages) == [9901, 9902, 9903]
    opened = next(e for e in events if isinstance(e, ErrorOpened) and e.message.code == 9901)
    assert opened.error.kind is ErrorKind.OTHER
    assert result.status is Status.FAILURE


def test_a_state_message_is_an_unknown_message_not_kept_as_unknown() -> None:
    # Package 13a: trace states are 13b's; a state message is shown as printed, and its code is in CODES.
    result, events = _drive(BUILDS["v1.7.4"] / "violation.out")
    states = [e for e in events if isinstance(e, UnknownMessage)]
    assert [e.message.code for e in states] == [2217] * 4
    assert result.unknown_messages == []


# --- The output bound ---------------------------------------------------------------------------------------------


def test_the_output_keeps_the_newest_lines_and_counts_the_rest() -> None:
    path = BUILDS["v1.7.4"] / "print-output.out"
    full, _ = _drive(path)
    result, events = _drive(path, TlcParser(max_output_lines=2))
    assert len(full.output) > 2
    assert result.output == full.output[-2:]
    assert result.output_dropped == len(full.output) - 2
    assert _outputs(events) == full.output


# --- Events in order --------------------------------------------------------------------------------------------


@pytest.mark.parametrize("build", sorted(BUILDS))
def test_related_messages_extend_the_error_in_arrival_order(build: str) -> None:
    _, events = _drive(BUILDS[build] / "assertion-failure.out")
    errors = [(type(e).__name__, e.message.code) for e in events if isinstance(e, ErrorOpened | ErrorExtended)]
    assert errors == [("ErrorOpened", 2132), ("ErrorExtended", 2121), ("ErrorExtended", 2103)]


@pytest.mark.parametrize("build", sorted(BUILDS))
def test_the_sany_diagnostic_comes_before_the_end_of_the_window(build: str) -> None:
    _, events = _drive(BUILDS[build] / "sany-semantic-error.out")
    found = next(i for i, e in enumerate(events) if isinstance(e, DiagnosticFound))
    window_end = next(i for i, e in enumerate(events) if isinstance(e, PhaseChanged) and e.message.code == 2219)
    assert found < window_end


@pytest.mark.parametrize("build", sorted(BUILDS))
@pytest.mark.parametrize("case", ["sany-semantic-error", "parse-error"])
def test_reading_the_diagnostics_after_every_line_changes_nothing(build: str, case: str) -> None:
    path = BUILDS[build] / f"{case}.out"
    plain, _ = _drive(path)
    parser = TlcParser()
    seen: list[int] = []
    for line in read_lines(path):
        parser.feed(line)
        seen.append(len(list(parser.result.sany)))
    parser.close()
    assert parser.result.to_dict() == plain.to_dict()
    assert len(parser.result.sany) == 1
    assert seen[-1] == 1


# --- Checkpoints and recovery -----------------------------------------------------------------------------------


@pytest.mark.parametrize("build", sorted(BUILDS))
def test_a_checkpoint_is_started_with_its_folder_and_written(build: str) -> None:
    _, events = _drive(BUILDS[build] / "checkpoint-run.out")
    started = [e for e in events if isinstance(e, CheckpointStarted)]
    assert len(started) == 1
    assert started[0].folder.split("/")[-2] == "checkpoint-run"
    assert not started[0].folder.endswith("/")
    after = events[events.index(started[0]) + 1 :]
    assert [type(e) for e in after if isinstance(e, CheckpointWritten)] == [CheckpointWritten]


# The two numbers of 2198, "Recovery completed. N states examined. M states on queue.": v1.7.4:45, rolling:47.
RECOVERED = {"v1.7.4": (896, 1), "2026.11.15.002146": (874, 1)}


@pytest.mark.parametrize("build", sorted(BUILDS))
def test_recovery_gives_the_two_numbers_and_sets_resumed(build: str) -> None:
    result, events = _drive(BUILDS[build] / "checkpoint-recover.out")
    recovered = [(e.message.code, e.examined, e.queued) for e in events if isinstance(e, Recovered)]
    assert recovered == [(2197, None, None), (2198, *RECOVERED[build])]
    assert result.resumed


# --- Cases the design calls "not seen" (package 13): no raise, every message carried ------------------------------


def test_feeding_after_close_and_a_second_sany_window_lose_nothing() -> None:
    path = BUILDS["v1.7.4"] / "success.out"
    parser = TlcParser()
    _, first = _drive(path, parser)
    _, second = _drive(path, parser)
    # The second 2220 opens no window: the SANY lines after it are the spec's output (P8, "shut for good").
    assert len(_outputs(second)) == parser.result.unframed_lines - parser.result.sany_lines_used
    assert _outputs(first) == []
    assert all(isinstance(e, OutputLine) or _message(e) is not None for e in second)
    assert parser.result.phase is Phase.FINISHED
    assert not any(isinstance(e, Information) and e.message.code in (2220, 2219) for e in second)
