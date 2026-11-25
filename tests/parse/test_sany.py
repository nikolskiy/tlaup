"""The SANY parser on the golden captures of SANY alone (design 10 P8, 21 S5, package 12).

Plain pytest over ``tests/parse/golden/sany/<build>/``: each file is read in binary, split into lines that keep
their line ending, decoded as UTF-8 with ``errors="replace"`` and fed one line per call; ``close()`` comes last.
The expectations are written from reading the captures (question Q18), not taken from the parser's output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tlaup_parse import Diagnostic, Location, SanyLineClass, SanyParser, SanyResult, SanyStep

SANY = Path(__file__).resolve().parent / "golden" / "sany"
BUILDS = {"v1.7.4": SANY / "v1.7.4", "rolling": SANY / "2026.11.15.002146"}
ALL_FILES = [(build, path) for build, folder in BUILDS.items() for path in sorted(folder.glob("*.out"))]
ALL_IDS = [f"{build}/{path.stem}" for build, path in ALL_FILES]


def read_lines(path: Path) -> list[str]:
    return [raw.decode("utf-8", errors="replace") for raw in path.read_bytes().splitlines(keepends=True)]


def drive(lines: list[str]) -> tuple[SanyParser, list[SanyStep]]:
    parser = SanyParser()
    steps = [parser.feed(line) for line in lines]
    steps.append(parser.close())
    return parser, steps


def run(build: str, case: str) -> tuple[SanyResult, list[SanyStep], list[str]]:
    lines = read_lines(BUILDS[build] / f"{case}.out")
    parser, steps = drive(lines)
    return parser.result, steps, lines


def result_of(build: str, case: str) -> SanyResult:
    return run(build, case)[0]


def loc(module: str, line: int, col: int, end_line: int | None, end_col: int | None) -> Location:
    return Location(module=module, line=line, column=col, end_line=end_line, end_column=end_col)


def shape(d: Diagnostic) -> tuple[str, str | None, Location | None, str]:
    return (d.severity, d.module, d.location, d.message)


def classes(steps: list[SanyStep]) -> list[SanyLineClass | None]:
    return [step.line_class for step in steps]


BOTH = pytest.mark.parametrize("build", list(BUILDS))

# ---------------------------------------------------------------------------------------------------------------
# Golden, SANY alone
# ---------------------------------------------------------------------------------------------------------------


@BOTH
def test_a_good_spec_has_no_diagnostics(build: str) -> None:
    result = result_of(build, "sany-good")
    assert result.diagnostics == ()
    assert result.other == ()


@BOTH
def test_two_semantic_errors_each_have_their_position(build: str) -> None:
    result = result_of(build, "sany-semerr")
    assert [shape(d) for d in result.diagnostics] == [
        ("error", "SemErr", loc("SemErr", 4, 13, 4, 13), "Unknown operator: `y'."),
        ("error", "SemErr", loc("SemErr", 5, 22, 5, 24), "Unknown operator: `Foo'."),
    ]
    assert {d.tool for d in result.diagnostics} == {"sany"}
    assert all(d.file is not None and d.file.endswith("SemErr.tla") for d in result.diagnostics)
    assert all(d.details == () for d in result.diagnostics)


@pytest.mark.parametrize(("build", "case"), [("v1.7.4", "sany-levelerr-174"), ("rolling", "sany-levelerr")])
def test_two_level_errors_with_two_line_messages(build: str, case: str) -> None:
    result = result_of(build, case)
    assert [shape(d) for d in result.diagnostics] == [
        (
            "error",
            "LevelErr",
            loc("LevelErr", 6, 8, 6, 10),
            "Level error in applying operator ':\n"
            "The level of argument 1 exceeds the maximum level allowed by the operator.",
        ),
        (
            "error",
            "LevelErr",
            loc("LevelErr", 4, 1, 4, 12),
            "Level error: assumptions must be level 0 (Constant),\nbut this one has level 1.",
        ),
    ]


@BOTH
def test_the_precedence_conflict_is_located_through_the_second_form(build: str) -> None:
    result = result_of(build, "sany-level")
    (diagnostic,) = result.diagnostics
    assert diagnostic.severity == "error"
    assert diagnostic.module == "Level"
    assert diagnostic.location == loc("Level", 6, 27, 6, 27)
    assert diagnostic.message == (
        "Precedence conflict between ops [] in block line 6, col 27 to line 6, col 27 of module Level and '."
    )
    assert diagnostic.details[0] == "ExtendableExpr starting at line 6, column 20."
    assert diagnostic.details[-1] == "Module body starting at line 3, column 1."
    assert len(diagnostic.details) == 5


@BOTH
def test_a_parse_error_has_module_location_and_residual_stack(build: str) -> None:
    result = result_of(build, "sany-parseerr")
    (diagnostic,) = result.diagnostics
    assert diagnostic.severity == "error"
    assert diagnostic.module == "ParseErr"
    assert diagnostic.file is not None and diagnostic.file.endswith("ParseErr.tla")
    assert diagnostic.location == loc("ParseErr", 4, 9, None, None)
    assert diagnostic.message == (
        'Was expecting "Expression or Instance"\n'
        'Encountered "Beginning of definition" at line 4, column 9 and token "=="'
    )
    assert diagnostic.details == (
        "Definition starting at line 4, column 1.",
        "Module body starting at line 3, column 1.",
        "Module definition starting at line 1, column 1.",
    )
    assert result.other == ()


@BOTH
def test_several_parse_errors_in_one_spec_give_one_diagnostic(build: str) -> None:
    result = result_of(build, "sany-multi")
    (diagnostic,) = result.diagnostics
    assert diagnostic.module == "Multi"
    assert diagnostic.location == loc("Multi", 7, 6, None, None)


@BOTH
def test_a_missing_module_gives_one_diagnostic_without_location(build: str) -> None:
    result = result_of(build, "sany-missingmod")
    (diagnostic,) = result.diagnostics  # rolling prints it twice
    assert diagnostic.severity == "error"
    assert diagnostic.location is None
    assert diagnostic.message == "Cannot find source file for module NoSuchModule imported in module MissingMod."
    file_lines = [line for line in result.other if line.startswith("File does not exist:")]
    assert len(file_lines) == (1 if build == "v1.7.4" else 0)


def test_the_missing_module_names_the_importing_module_on_rolling() -> None:
    (diagnostic,) = result_of("rolling", "sany-missingmod").diagnostics
    assert diagnostic.module == "MissingMod"
    assert diagnostic.file is not None and diagnostic.file.endswith("MissingMod.tla")


@BOTH
def test_a_name_mismatch_gives_one_diagnostic(build: str) -> None:
    result = result_of(build, "sany-namemismatch")
    (diagnostic,) = result.diagnostics
    assert diagnostic.severity == "error"
    assert diagnostic.location is None
    assert (
        diagnostic.message
        == "File name 'NameMismatch' does not match the name 'Other' of the top level module it contains."
    )


@BOTH
def test_a_missing_file_gives_one_diagnostic_and_the_stderr_line_is_other(build: str) -> None:
    result = result_of(build, "sany-nofile")
    (diagnostic,) = result.diagnostics
    assert shape(diagnostic) == ("error", None, None, "Cannot find the specified file Nope.tla.")
    assert diagnostic.file is None
    assert [line for line in result.other if line] and result.other[0].startswith("File does not exist: ")


@BOTH
def test_message_4802_is_an_error(build: str) -> None:
    result = result_of(build, "sany-warn4802")
    assert [shape(d) for d in result.diagnostics] == [
        ("error", "Warn4802", loc("Warn4802", 4, 16, 4, 16), "Non-unique fields in constructor.")
    ]
    (clash,) = result_of(build, "sany-warning-recclash").diagnostics
    assert clash.severity == "error"
    assert clash.module == "RecClash"
    assert clash.location == loc("RecClash", 3, 16, 3, 16)


@BOTH
def test_the_two_stuttering_lints_are_errors(build: str) -> None:
    result = result_of(build, "sany-warn")
    assert [shape(d) for d in result.diagnostics] == [
        ("error", "Warn", loc("Warn", 6, 9, 6, 22), "[] followed by action not of form [A]_v."),
        ("error", "Warn", loc("Warn", 7, 10, 7, 19), "<> followed by action not of form <<A>>_v."),
    ]


def test_two_files_on_one_command_line_give_two_banners_and_find_the_second_files_errors() -> None:
    result, steps, _ = run("rolling", "sany-goodthenbad")
    assert classes(steps).count(SanyLineClass.BANNER) == 2
    assert [shape(d) for d in result.diagnostics] == [
        ("error", "SemErr", loc("SemErr", 4, 13, 4, 13), "Unknown operator: `y'."),
        ("error", "SemErr", loc("SemErr", 5, 22, 5, 24), "Unknown operator: `Foo'."),
    ]
    assert set(result.module_files) >= {"Good", "SemErr", "Naturals"}
    assert result.diagnostics[0].file is not None and result.diagnostics[0].file.endswith("SemErr.tla")


def test_a_bad_file_then_a_good_one_keeps_the_first_files_error() -> None:
    result, steps, _ = run("rolling", "sany-badthengood")
    assert classes(steps).count(SanyLineClass.BANNER) == 1
    (diagnostic,) = result.diagnostics
    assert diagnostic.module == "ParseErr"


def test_two_banners_on_rolling_with_clean_files_give_nothing() -> None:
    result, steps, _ = run("rolling", "sany-twofiles")
    assert classes(steps).count(SanyLineClass.BANNER) == 2
    assert result.diagnostics == ()
    assert set(result.module_files) == {"Good", "Naturals", "Two"}


STALE = {
    "sany-stale-alg": (
        "PcalStaleAlg",
        "The PlusCal algorithm in module PcalStaleAlg has changed since its last translation.",
    ),
    "sany-stale-tla": (
        "PcalStaleTla",
        "The TLA+ translation in module PcalStaleTla has changed since its last translation.",
    ),
}
STALE_BOTH = {
    "v1.7.4": (
        "The PlusCal algorithm and its TLA+ translation in module PcalStaleBoth filename since the last translation."
    ),
    "rolling": (
        "Both the PlusCal algorithm and its TLA+ translation in module PcalStaleBoth "
        "have changed since the last translation."
    ),
}


@BOTH
@pytest.mark.parametrize("case", sorted(STALE))
def test_the_stale_translation_warning_has_its_module_and_text(build: str, case: str) -> None:
    module, text = STALE[case]
    result = result_of(build, case)
    (diagnostic,) = result.diagnostics
    assert diagnostic.severity == "warning"
    assert diagnostic.tool == "sany"
    assert diagnostic.module == module
    assert diagnostic.location is None
    assert diagnostic.message == text
    assert diagnostic.file is not None and diagnostic.file.endswith(f"{module}.tla")
    assert result.other == ()


@BOTH
def test_the_both_changed_warning_is_kept_as_printed(build: str) -> None:
    (diagnostic,) = result_of(build, "sany-stale-both").diagnostics
    assert shape(diagnostic) == ("warning", "PcalStaleBoth", None, STALE_BOTH[build])


@BOTH
def test_two_stale_warnings_from_two_files(build: str) -> None:
    result = result_of(build, "sany-stale-two-files")
    assert [(d.severity, d.module, d.message) for d in result.diagnostics] == [
        ("warning", "PcalStaleAlg", STALE["sany-stale-alg"][1]),
        ("warning", "PcalStaleTla", STALE["sany-stale-tla"][1]),
    ]
    assert [d.file is not None and d.file.endswith(f"{d.module}.tla") for d in result.diagnostics] == [True, True]


NO_DIAGNOSTICS = [
    ("v1.7.4", "sany-help"),
    ("rolling", "sany-help"),
    ("v1.7.4", "sany-h"),
    ("rolling", "sany-h"),
    ("v1.7.4", "sany-grouped-dl"),
    ("rolling", "sany-grouped-dl"),
    ("v1.7.4", "sany-grouped-unknown"),
    ("rolling", "sany-grouped-unknown"),
    ("rolling", "sany-noargs"),
]


@pytest.mark.parametrize(("build", "case"), NO_DIAGNOSTICS)
def test_help_and_refused_options_have_no_diagnostics_and_every_line_is_other(build: str, case: str) -> None:
    result, steps, lines = run(build, case)
    assert result.diagnostics == ()
    assert [line for line in result.other if line] == [line.rstrip() for line in lines if line.strip()]
    assert SanyLineClass.BANNER not in classes(steps)


def test_the_help_page_keeps_its_ansi_codes() -> None:
    result = result_of("rolling", "sany-help")
    assert any("\x1b[1m" in line for line in result.other)


def test_the_illegal_switch_line_is_other() -> None:
    assert result_of("v1.7.4", "sany-help").other[0] == "Illegal switch: -help"


def test_no_arguments_on_v1_7_4_prints_nothing() -> None:
    result = result_of("v1.7.4", "sany-noargs")
    assert result == SanyResult(diagnostics=(), module_files={}, other=(), lines_used=0)


def test_module_files_come_from_the_parsing_file_lines() -> None:
    result = result_of("rolling", "sany-semerr")
    assert set(result.module_files) == {"SemErr", "Naturals"}
    assert result.module_files["SemErr"].endswith("SemErr.tla")
    assert " (jar:" not in result.module_files["Naturals"]
    assert result.module_files["Naturals"].endswith("Naturals.tla")


def test_a_warning_block_header_gives_no_file(tmp_path: Path) -> None:
    parser = SanyParser()
    for line in ["Warnings (1) during syntax parsing of Other.tla:\n", "\n", "In module Other\n", "\n", "Careful.\n"]:
        parser.feed(line)
    (diagnostic,) = parser.close().diagnostics
    assert (diagnostic.severity, diagnostic.module, diagnostic.file, diagnostic.message) == (
        "warning",
        "Other",
        None,
        "Careful.",
    )


def test_classes_of_a_semantic_error_capture() -> None:
    _, steps, lines = run("v1.7.4", "sany-semerr")
    got = [(line.rstrip(), step.line_class) for line, step in zip(lines, steps, strict=False)]
    assert got[0] == ("", SanyLineClass.BLANK)
    assert got[1][1] is SanyLineClass.BANNER
    assert got[3][1] is SanyLineClass.PROGRESS  # Parsing file
    assert ("Semantic errors:", SanyLineClass.HEADER) in got
    assert ("*** Errors: 2", SanyLineClass.STRUCTURE) in got
    assert ("line 4, col 13 to line 4, col 13 of module SemErr", SanyLineClass.POSITION) in got
    assert ("Unknown operator: `y'.", SanyLineClass.MESSAGE) in got
    assert steps[-1].line_class is None


def test_an_empty_line_after_an_other_line_is_other() -> None:
    parser = SanyParser()
    assert parser.feed("something odd\n").line_class is SanyLineClass.OTHER
    assert parser.feed("\n").line_class is SanyLineClass.OTHER
    assert parser.feed("\n").line_class is SanyLineClass.OTHER
    assert parser.feed("Semantic processing of module M\n").line_class is SanyLineClass.PROGRESS
    assert parser.feed("\n").line_class is SanyLineClass.BLANK
    assert parser.result.other == ("something odd", "", "")


def test_a_location_line_inside_the_parse_states_is_an_ordinary_line() -> None:
    parser = SanyParser()
    parser.feed("***Parse Error***\n")
    step = parser.feed("line 6, col 27 to line 6, col 27 of module Level\n")
    assert step.line_class is SanyLineClass.MESSAGE
    parser.feed("Residual stack trace follows:\n")
    step = parser.feed("line 1, col 1 to line 1, col 2 of module Level\n")
    assert step.line_class is SanyLineClass.MESSAGE


def test_a_location_with_no_text_under_it_is_dropped_but_counted_as_used() -> None:
    parser = SanyParser()
    parser.feed("Semantic errors:\n")
    parser.feed("line 4, col 13 to line 4, col 13 of module M\n")
    parser.feed("\n")
    step = parser.feed("*** Errors: 1\n")
    assert step.diagnostics == ()
    parser.close()
    assert parser.result.diagnostics == ()
    assert parser.result.other == ()
    assert parser.result.lines_used == 4


def test_close_returns_a_parse_error_without_module_when_the_input_ends_early() -> None:
    lines = read_lines(BUILDS["v1.7.4"] / "sany-parseerr.out")
    stop = next(i for i, line in enumerate(lines) if line.startswith("Fatal errors"))
    parser = SanyParser()
    for line in lines[:stop]:
        assert parser.feed(line).diagnostics == ()
    step = parser.close()
    assert step.line_class is None
    (diagnostic,) = step.diagnostics
    assert diagnostic.module is None
    assert diagnostic.location is not None and (diagnostic.location.line, diagnostic.location.column) == (4, 9)
    assert len(diagnostic.details) == 3


def test_a_diagnostic_is_returned_when_it_completes_not_after_every_line() -> None:
    _, steps, lines = run("v1.7.4", "sany-semerr")
    returned = [(i, d) for i, step in enumerate(steps) for d in step.diagnostics]
    assert len(returned) == 2
    # the first is returned by the second location line, the second by the end of the input
    assert lines[returned[0][0]].startswith("line 5, col 22")
    assert returned[1][0] == len(lines)


# ---------------------------------------------------------------------------------------------------------------
# Properties over every golden file
# ---------------------------------------------------------------------------------------------------------------


@pytest.fixture(params=ALL_FILES, ids=ALL_IDS)
def golden(request: pytest.FixtureRequest) -> Path:
    path: Path = request.param[1]
    return path


def test_other_lines_equal_the_result_and_lines_used_completes_the_count(golden: Path) -> None:
    lines = read_lines(golden)
    parser, steps = drive(lines)
    result = parser.result
    others = tuple(
        line.rstrip() for line, step in zip(lines, steps, strict=False) if step.line_class is SanyLineClass.OTHER
    )
    assert result.other == others
    assert result.lines_used + len(result.other) == len(lines)
    assert steps[-1].line_class is None
    assert all(step.line_class is not None for step in steps[:-1])


def test_returned_diagnostics_are_the_result_in_order_and_none_twice(golden: Path) -> None:
    _, steps = drive(read_lines(golden))
    returned = tuple(d for step in steps for d in step.diagnostics)
    parser, _ = drive(read_lines(golden))
    assert returned == parser.result.diagnostics
    assert len(set(returned)) == len(returned)


def test_line_endings_do_not_matter(golden: Path) -> None:
    bare = [line.rstrip("\r\n") for line in read_lines(golden)]
    results = [drive([line + ending for line in bare])[0].result for ending in ("\n", "", "\r\n")]
    assert results[0] == results[1] == results[2]


def test_reading_the_result_after_every_line_changes_nothing(golden: Path) -> None:
    lines = read_lines(golden)
    quiet, _ = drive(lines)
    watched = SanyParser()
    for line in lines:
        watched.feed(line)
        _ = watched.result
    watched.close()
    assert watched.result == quiet.result


def test_the_dictionary_form_is_json_and_round_trips(golden: Path) -> None:
    result = drive(read_lines(golden))[0].result
    data = result.to_dict()
    assert set(data) == {"diagnostics", "module_files", "other", "lines_used"}
    assert json.loads(json.dumps(data)) == data
    assert SanyResult.from_dict(data) == result
    assert SanyResult.from_dict(json.loads(json.dumps(data))) == result


def test_the_dictionary_of_an_empty_result_leaves_nothing_out() -> None:
    assert SanyParser().result.to_dict() == {"diagnostics": [], "module_files": {}, "other": [], "lines_used": 0}


def test_the_dictionary_form_of_a_diagnostic_is_the_models() -> None:
    result = result_of("v1.7.4", "sany-semerr")
    assert result.to_dict()["diagnostics"] == [d.to_dict() for d in result.diagnostics]


def test_a_line_class_dictionary_value_is_its_lower_case_name() -> None:
    assert all(c.value == c.name.lower() for c in SanyLineClass)
    assert {c.value for c in SanyLineClass} == {
        "banner",
        "progress",
        "header",
        "structure",
        "position",
        "message",
        "blank",
        "other",
    }


# ---------------------------------------------------------------------------------------------------------------
# Unit
# ---------------------------------------------------------------------------------------------------------------


@BOTH
def test_one_error_block_fed_twice_gives_the_diagnostic_once(build: str) -> None:
    lines = read_lines(BUILDS[build] / "sany-semerr.out")
    header = next(i for i, line in enumerate(lines) if line.startswith("Semantic errors:"))
    first = next(i for i, line in enumerate(lines) if line.startswith("line 4, col 13"))
    second = next(i for i, line in enumerate(lines) if line.startswith("line 5, col 22"))
    block = lines[first:second]
    parser = SanyParser()
    returned: list[Diagnostic] = []
    for line in [*lines[: header + 1], *block, *block, *lines[second:]]:
        returned.extend(parser.feed(line).diagnostics)
    returned.extend(parser.close().diagnostics)
    assert [d.location for d in returned] == [loc("SemErr", 4, 13, 4, 13), loc("SemErr", 5, 22, 5, 24)]
    assert parser.result.diagnostics == tuple(returned)


def test_a_parse_error_whose_message_has_no_position_has_no_location() -> None:
    parser = SanyParser()
    for line in ["***Parse Error***\n", "Something odd\n", "Residual stack trace follows:\n", "A frame.\n"]:
        parser.feed(line)
    (diagnostic,) = parser.close().diagnostics
    assert diagnostic.location is None
    assert diagnostic.details == ("A frame.",)
