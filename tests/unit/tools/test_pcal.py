"""`tools/pcal.py` (design 21 S2, decision D67): the pure helpers, and `run_pcal` with the fake `java` as a real child.

The run is under `signals_held` in the test process's main thread, as the launcher's tests are; no signal is sent.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from tests.fakes._fakelib import GOLDEN_DIR
from tlaup.java.launcher import JavaInvocation
from tlaup.tools.pcal import PcalOutcome, label_line, run_pcal, trim_full_stop, written_notes

if TYPE_CHECKING:
    from tests.fakes.control import Fakes
    from tlaup_parse import Diagnostic

ROLLING = GOLDEN_DIR / "pcal" / "2026.11.15.002146"
CWD = Path("/work")


# ---------------------------------------------------------------- the pure helpers


def test_a_doubled_full_stop_loses_one() -> None:
    assert trim_full_stop("Beginning of algorithm string --algorithm not found..") == (
        "Beginning of algorithm string --algorithm not found."
    )


def test_one_full_stop_or_none_is_unchanged() -> None:
    assert trim_full_stop("Could not find resource file Foo.tla.") == "Could not find resource file Foo.tla."
    assert trim_full_stop("Expected \"do\" but found ':='") == "Expected \"do\" but found ':='"


def test_the_notes_for_a_spec_in_the_starting_folder_are_in_the_translators_order() -> None:
    notes = written_notes(["Pcal.tla", "Pcal.cfg"], CWD / "Pcal.tla", CWD)
    assert notes == ["Pcal.tla translated (previous version saved as Pcal.old)", "Pcal.cfg written"]


def test_the_notes_for_a_spec_in_a_subfolder_are_relative_to_the_starting_folder() -> None:
    notes = written_notes(["Pcal.tla", "Pcal.cfg"], CWD / "sub" / "Pcal.tla", CWD)
    assert notes == [
        f"{Path('sub/Pcal.tla')} translated (previous version saved as Pcal.old)",
        f"{Path('sub/Pcal.cfg')} written",
    ]


def test_the_notes_for_a_spec_outside_the_starting_folder_are_absolute() -> None:
    other = Path("/elsewhere")
    notes = written_notes(["Pcal.tla", "Pcal.cfg"], other / "Pcal.tla", CWD)
    assert notes == [
        f"{other / 'Pcal.tla'} translated (previous version saved as Pcal.old)",
        f"{other / 'Pcal.cfg'} written",
    ]


def test_no_names_give_no_notes() -> None:
    assert written_notes([], CWD / "Pcal.tla", CWD) == []


def test_a_label_line_for_a_spec_in_the_starting_folder() -> None:
    assert label_line("Lbl_1", 7, 3, CWD / "PcalNoLabel.tla", CWD) == "PcalNoLabel.tla:7:3: label Lbl_1 added"


def test_a_label_line_is_relative_beneath_the_starting_folder_and_absolute_elsewhere() -> None:
    assert label_line("L", 1, 2, CWD / "sub" / "S.tla", CWD) == f"{Path('sub/S.tla')}:1:2: label L added"
    assert label_line("L", 1, 2, Path("/elsewhere/S.tla"), CWD) == f"{Path('/elsewhere/S.tla')}:1:2: label L added"


# ---------------------------------------------------------------- run_pcal with the fake java as a real child

pytestmark_posix = pytest.mark.skipif(os.name == "nt", reason="POSIX signals and process groups")


class Recorder:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []

    def other(self, line: str) -> None:
        self.calls.append(("other", line))

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        self.calls.append(("diagnostic", diagnostic))

    def label(self, name: str, line: int, column: int) -> None:
        self.calls.append(("label", name, line, column))

    def finish(self, outcome: PcalOutcome) -> None:
        self.calls.append(("finish", outcome))


def run(fakes: Fakes, build: Path, case: str, exit_code: int, spec: Path) -> Recorder:
    fakes.script("java", {"runs": [{"main": "pcal.trans", "stdout": str(build / f"{case}.out"), "exit": exit_code}]})
    java_inv = JavaInvocation(
        java=fakes.bin / "java",
        jvm_options=(),
        system_properties=(),
        classpath=(),
        main_class="pcal.trans",
        args=(spec.name,),
    )
    inv: Any = SimpleNamespace(spec=spec)
    recorder = Recorder()
    outcome = run_pcal(inv, java_inv, recorder, recorder.finish)
    assert outcome.exit_code == exit_code
    return recorder


@pytestmark_posix
def test_a_diagnostic_and_its_continuation_lines_come_in_the_translators_order(fakes: Fakes) -> None:
    spec = Path("/work/PcalProc.tla")
    recorder = run(fakes, ROLLING, "pcal-spec", 255, spec)
    shape = [c[0] if c[0] != "other" else c[1] for c in recorder.calls]
    assert shape == [
        "Wrote file AST.tla.",
        "",
        "diagnostic",
        "    There is probably something wrong with the way",
        "    the +cal translator is installed.",
        "",
        "finish",
    ]
    diagnostic = recorder.calls[2][1]
    assert diagnostic.file == str(spec)
    assert diagnostic.message == "Could not find resource file Foo.tla."


@pytestmark_posix
def test_a_good_translation_calls_no_sink_method_and_finishes_with_both_files(fakes: Fakes) -> None:
    recorder = run(fakes, ROLLING, "pcal-good", 0, Path("/work/Pcal.tla"))
    assert [call[0] for call in recorder.calls] == ["finish"]
    assert recorder.calls[0][1].result.files_written == ["Pcal.tla", "Pcal.cfg"]


@pytestmark_posix
def test_an_added_label_is_one_label_call_and_no_other_call(fakes: Fakes) -> None:
    recorder = run(fakes, ROLLING, "pcal-label", 0, Path("/work/PcalNoLabel.tla"))
    assert [call[:4] for call in recorder.calls if call[0] != "finish"] == [("label", "Lbl_1", 7, 3)]
    assert recorder.calls[-1][0] == "finish"
