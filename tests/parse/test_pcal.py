"""The PlusCal parser on the golden captures of the translator (design 10 P2, 21 S2 and S5, package 14).

Plain pytest over ``tests/parse/golden/pcal/<build>/``: each file is read in binary, split into lines that keep
their line ending, decoded as UTF-8 with ``errors="replace"`` and fed one line per call; ``close()`` comes last.
The expectations are written from reading the captures (question Q18), not taken from the parser's output.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tests.parse.drive import cases_of, golden_root, read_lines
from tlaup_parse import Diagnostic, Location, PcalParser, PcalResult

if TYPE_CHECKING:
    from pathlib import Path

PCAL = golden_root() / "pcal"
BUILDS = {"v1.7.4": PCAL / "v1.7.4", "rolling": PCAL / "2026.11.15.002146"}
BANNERS = {"v1.7.4": "1.11 of 31 December 2020", "rolling": "1.12 of 01 July 2024"}
ALL_FILES = [(build, path) for build, folder in BUILDS.items() for path in sorted(folder.glob("*.out"))]
ALL_IDS = [f"{build}/{path.stem}" for build, path in ALL_FILES]
BOTH = pytest.mark.parametrize("build", list(BUILDS))
EVERY = pytest.mark.parametrize(("build", "path"), ALL_FILES, ids=ALL_IDS)


def drive(lines: list[str]) -> tuple[PcalParser, list[list[Diagnostic]]]:
    parser = PcalParser()
    returned = [parser.feed(line) for line in lines]
    returned.append(parser.close())
    return parser, returned


def run(build: str, case: str) -> PcalResult:
    return drive(read_lines(BUILDS[build] / f"{case}.out"))[0].result


def loc(line: int, column: int) -> Location:
    return Location(module="", line=line, column=column, end_line=None, end_column=None)


def shape(d: Diagnostic) -> tuple[str, str, str | None, str | None, Location | None, tuple[str, ...]]:
    return (d.tool, d.severity, d.module, d.file, d.location, d.details)


def only_diagnostic(result: PcalResult) -> Diagnostic:
    assert len(result.diagnostics) == 1
    return result.diagnostics[0]


def test_every_build_has_the_same_cases() -> None:
    names = [sorted(p.stem for p in folder.glob("*.out")) for folder in BUILDS.values()]
    assert names[0] == names[1]
    assert len(names[0]) == 18


# ---------------------------------------------------------------------------------------------------------------
# Golden cases
# ---------------------------------------------------------------------------------------------------------------


@BOTH
def test_a_good_spec_gives_the_version_and_the_two_files(build: str) -> None:
    result = run(build, "pcal-good")
    assert result.version == BANNERS[build]
    assert result.files_written == ["Pcal.tla", "Pcal.cfg"]
    assert result.labels_added == []
    assert result.diagnostics == []
    assert result.other == []


@BOTH
def test_nocfg_writes_the_tla_file_only(build: str) -> None:
    assert run(build, "pcal-nocfg").files_written == ["Pcal.tla"]


@BOTH
def test_a_syntax_error_has_its_message_and_position(build: str) -> None:
    result = run(build, "pcal-syntaxerr")
    diagnostic = only_diagnostic(result)
    assert diagnostic.message == 'Expected "do" but found ":="'
    assert shape(diagnostic) == ("pcal", "error", None, None, loc(6, 20), ())
    assert result.files_written == []
    assert result.other == []


@BOTH
def test_an_undeclared_variable_uses_the_at_line_form(build: str) -> None:
    diagnostic = only_diagnostic(run(build, "pcal-semerr"))
    assert diagnostic.message == "Assignment to undeclared variable y"
    assert diagnostic.location == loc(6, 6)


@BOTH
def test_no_algorithm_gives_a_message_without_a_location(build: str) -> None:
    diagnostic = only_diagnostic(run(build, "pcal-noalg"))
    assert diagnostic.message.endswith("not found..")
    assert diagnostic.location is None


@BOTH
def test_a_missing_label_has_a_position_on_an_indented_line(build: str) -> None:
    diagnostic = only_diagnostic(run(build, "pcal-nolabel"))
    assert diagnostic.message == "Missing label at the following location:"
    assert diagnostic.location == loc(7, 3)


@BOTH
def test_report_labels_gives_the_label_then_the_files(build: str) -> None:
    result = run(build, "pcal-label")
    assert result.labels_added == [("Lbl_1", 7, 3)]
    assert result.files_written == ["PcalNoLabel.tla", "PcalNoLabel.cfg"]
    assert result.diagnostics == []
    assert result.other == []


@pytest.mark.parametrize(
    ("build", "message"),
    [
        ("v1.7.4", "Command-line error: Input file Nope.pcal and Nope.tla.tla not found.."),
        ("rolling", "Input file Nope.tla not found."),
    ],
)
def test_a_missing_file_differs_by_build(build: str, message: str) -> None:
    diagnostic = only_diagnostic(run(build, "pcal-nofile"))
    assert diagnostic.message == message
    assert diagnostic.location is None


@BOTH
def test_an_unknown_option(build: str) -> None:
    diagnostic = only_diagnostic(run(build, "pcal-badopt"))
    assert diagnostic.message == "Command-line error: Unknown command-line option: -bogus.."
    assert diagnostic.location is None


@BOTH
def test_no_arguments(build: str) -> None:
    diagnostic = only_diagnostic(run(build, "pcal-noargs"))
    assert diagnostic.message == "Command-line error: No arguments specified.."
    assert diagnostic.location is None


@BOTH
def test_write_ast_is_not_a_written_file(build: str) -> None:
    result = run(build, "pcal-writeast")
    assert result.diagnostics == []
    assert result.files_written == []
    assert result.other == ["Wrote file AST.tla."]


@BOTH
@pytest.mark.parametrize("case", ["pcal-err", "pcal-noext", "pcal-wf", "pcal-proc-wf", "pcal-termination"])
def test_the_other_successful_cases_write_two_files(build: str, case: str) -> None:
    result = run(build, case)
    assert result.version == BANNERS[build]
    assert len(result.files_written) == 2
    assert result.diagnostics == []


@BOTH
def test_a_message_on_three_lines_keeps_the_continuation_lines_as_other(build: str) -> None:
    result = run(build, "pcal-spec")
    diagnostic = only_diagnostic(result)
    assert diagnostic.message == "Could not find resource file Foo.tla."
    assert diagnostic.location is None
    assert result.files_written == []
    lines = read_lines(BUILDS[build] / "pcal-spec.out")
    ast = lines.index("Wrote file AST.tla.\n")
    # Wrote file AST.tla., its empty line, then the two continuation lines and the empty line after them.
    assert result.other == [line.rstrip() for line in lines[ast:] if not line.startswith(("Unrecoverable", " -- "))]
    assert result.other[0] == "Wrote file AST.tla."
    assert result.other[1] == ""
    assert result.other[-1] == ""
    assert len(result.other) == 5


@BOTH
def test_help_keeps_every_line_after_the_banner(build: str) -> None:
    lines = read_lines(BUILDS[build] / "pcal-help.out")
    result = run(build, "pcal-help")
    assert result.version == BANNERS[build]
    assert result.diagnostics == []
    assert result.other == [line.rstrip() for line in lines[1:]]
    assert "" in result.other


# ---------------------------------------------------------------------------------------------------------------
# Properties over every capture
# ---------------------------------------------------------------------------------------------------------------


@EVERY
def test_line_endings_do_not_change_the_result(build: str, path: Path) -> None:
    lines = [line.rstrip("\r\n") for line in read_lines(path)]
    results = [drive([line + ending for line in lines])[0].result for ending in ("\n", "", "\r\n")]
    assert results[0] == results[1] == results[2]


@EVERY
def test_returned_diagnostics_are_exactly_the_result_diagnostics(build: str, path: Path) -> None:
    parser, returned = drive(read_lines(path))
    assert [d for batch in returned for d in batch] == parser.result.diagnostics


@EVERY
def test_reading_the_result_after_every_line_changes_nothing(build: str, path: Path) -> None:
    lines = read_lines(path)
    plain = drive(lines)[0].result
    parser = PcalParser()
    for line in lines:
        parser.feed(line)
        _ = parser.result
    parser.close()
    assert parser.result == plain


@EVERY
def test_other_grows_as_lines_are_fed(build: str, path: Path) -> None:
    parser = PcalParser()
    other = parser.result.other
    for line in read_lines(path):
        parser.feed(line)
        assert parser.result.other is other
    parser.close()
    assert parser.result.other is other


@EVERY
def test_files_written_were_there_afterwards(build: str, path: Path) -> None:
    case = cases_of(BUILDS[build])[path.stem]
    after = case.get("files_after")
    if after is None:
        pytest.skip("no files_after in cases.toml")
    assert set(drive(read_lines(path))[0].result.files_written) <= set(after)  # type: ignore[arg-type]


@EVERY
def test_the_dictionary_form_is_json_and_round_trips(build: str, path: Path) -> None:
    result = drive(read_lines(path))[0].result
    data = result.to_dict()
    assert json.loads(json.dumps(data)) == data
    assert set(data) == {"version", "files_written", "labels_added", "diagnostics", "other"}
    assert PcalResult.from_dict(data) == result
    assert PcalResult.from_dict(json.loads(json.dumps(data))) == result


# ---------------------------------------------------------------------------------------------------------------
# The plural heading (no capture has it)
# ---------------------------------------------------------------------------------------------------------------


@BOTH
def test_the_label_lines_of_the_capture_give_one_label(build: str) -> None:
    assert run(build, "pcal-label").labels_added == [("Lbl_1", 7, 3)]


@BOTH
def test_the_plural_heading_with_a_repeated_label_line_gives_both_labels(build: str) -> None:
    lines = read_lines(BUILDS[build] / "pcal-label.out")
    heading = lines.index("The following label was added:\n")
    edited = list(lines)
    edited[heading] = "The following labels were added:\n"
    edited.insert(heading + 2, lines[heading + 1].replace("Lbl_1", "Lbl_2"))
    result = drive(edited)[0].result
    assert result.labels_added == [("Lbl_1", 7, 3), ("Lbl_2", 7, 3)]
    assert result.files_written == ["PcalNoLabel.tla", "PcalNoLabel.cfg"]
    assert result.other == []
    assert result.diagnostics == []
