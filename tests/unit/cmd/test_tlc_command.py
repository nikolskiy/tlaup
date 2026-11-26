"""`tlaup tlc` where a feature scenario cannot reach: two results compared with each other, and `print_run_notes`.

Design 11 R9 and 20 G1 (the printed command is the command that runs), 11 R6 (the values tlaup draws for -fp and
-seed are the ones it records and repeats), 10 P3 (the warning when TLC's exit code and its output disagree). The
runs go in-process through the app with the fake `java`, set up by the feature steps' own helpers; every store the
steps build has an injected clock. One test starts a fresh interpreter, to see which modules a run imports (14 F9).
"""

from __future__ import annotations

import io
import json
import os
import re
import shlex
import subprocess
import sys
from typing import TYPE_CHECKING, Any

import pytest

from tests.parse.drive import golden_root, read_lines
from tests.steps import _store
from tlaup.cmd.tlc import disagreement, print_run_notes
from tlaup.tlc.runner import RunOutcome
from tlaup.ui import Ui
from tlaup_parse import RunResult, TlcParser, Verdict

if TYPE_CHECKING:
    from tests.steps._scenario import Scenario

pytestmark = pytest.mark.skipif(os.name == "nt", reason="the command lines are compared in POSIX form (D15)")

_AGENT = re.compile(r"^-javaagent:")


def _set_up(scenario: Scenario) -> None:
    _store.install(scenario, "v1.7.4", pinned=True)
    scenario.spec_from_golden("Slow")


def _logged(scenario: Scenario) -> list[str]:
    return [str(arg) for arg in scenario.last_tool_start()["args"]]


def _without_run_id(args: list[str], runs: str) -> list[str]:
    """The arguments with the run id of the run folder under ``runs`` replaced, which differs from run to run."""
    return [re.sub(rf"^{re.escape(runs)}/[^/]+", f"{runs}/<run-id>", arg) for arg in args]


def _value_after(args: list[str], flag: str) -> str:
    assert args.count(flag) == 1, args
    return args[args.index(flag) + 1]


def test_show_command_prints_the_command_a_run_starts(scenario: Scenario) -> None:
    """R9 and G1: the printed line, read back by a shell, is the logged command less the lifeline agent."""
    _set_up(scenario)
    scenario.java_replays("tlc/v1.7.4/success", 0)
    options, tlc_args = "--cfg Slow.cfg --coverage --java-opt=-Xss8m", "-- -deadlock -fp 3 -seed 7"

    shown = scenario.run_in_process(f"tlaup tlc Slow {options} --show-command {tlc_args}")
    assert shown.exit_code == 0, shown.stderr
    assert shown.stdout is not None
    assert len(shown.stdout.splitlines()) == 1
    printed = shlex.split(shown.stdout)

    ran = scenario.run_in_process(f"tlaup tlc Slow {options} {tlc_args}")
    assert ran.exit_code == 0, ran.stderr
    logged = _logged(scenario)
    runs = str(scenario.paths().runs)

    assert printed[0] == scenario.last_tool_start()["path"]
    assert _without_run_id(printed[1:], runs) == _without_run_id([a for a in logged if not _AGENT.match(a)], runs)


def test_the_drawn_fp_and_seed_are_recorded_repeated_and_passed_on_resume(scenario: Scenario) -> None:
    """R6: a kept run's run.json and resume command hold the -fp and -seed its command had; a resume passes them."""
    _set_up(scenario)
    scenario.java_replays("tlc/v1.7.4/checkpoint-run", 255)
    scenario.metadir_files("queue.chkpt, vars.chkpt")

    first = scenario.run_in_process("tlaup tlc Slow --keep")
    assert first.exit_code == 255, first.stderr
    args = _logged(scenario)
    fp, seed = _value_after(args, "-fp"), _value_after(args, "-seed")
    kept = scenario.kept()
    record: dict[str, Any] = json.loads((kept / "run.json").read_text(encoding="utf-8"))
    assert (str(record["fp"]), str(record["seed"])) == (fp, seed)
    assert first.stderr is not None
    resume = next(line for line in first.stderr.splitlines() if line.startswith("Resume with: "))
    resume_words = shlex.split(resume.removeprefix("Resume with: "))
    assert (_value_after(resume_words, "-fp"), _value_after(resume_words, "-seed")) == (fp, seed)

    scenario.java_replays("tlc/v1.7.4/checkpoint-recover", 0)
    second = scenario.run_in_process(f"tlaup tlc Slow -- -recover {kept}/checkpoint")
    assert second.exit_code == 0, second.stderr
    resumed = _logged(scenario)
    assert (_value_after(resumed, "-fp"), _value_after(resumed, "-seed")) == (fp, seed)
    assert not kept.exists()


# P3: print_run_notes


def _ui() -> tuple[Ui, io.StringIO, io.StringIO]:
    out, err = io.StringIO(), io.StringIO()
    return Ui(out, err, io.StringIO(), color=False, env={}, terminal=False, size=(100, 30)), out, err


def _outcome(result: RunResult | None, code: int, **changes: Any) -> RunOutcome:
    values: dict[str, Any] = {
        "result": result,
        "exit_code": code,
        "tool_exit_code": code,
        "stopped_by": None,
        "stderr_tail": (),
        "warnings": (),
        "run_folder_kept": None,
        "resume_command": None,
        "dropped_checkpoint": None,
        "stopped_for_closed_pipe": False,
        "kept": None,
    }
    values.update(changes)
    return RunOutcome(**values)


def _two_errors() -> RunResult:
    """The result of the golden case that exits 0 with two errors (`deadlock-flag-multierror`)."""
    parser = TlcParser()
    for line in read_lines(golden_root() / "tlc" / "v1.7.4" / "deadlock-flag-multierror.out"):
        parser.feed(line)
    parser.close()
    assert parser.result.verdict is Verdict.ERRORS
    assert len(parser.result.errors) == 2
    return parser.result


@pytest.mark.parametrize(
    ("result", "code", "expected"),
    [
        pytest.param(_two_errors(), 0, "warning: TLC exited with 0, but its output reports 2 errors\n", id="0-errors"),
        pytest.param(
            RunResult(verdict=Verdict.NO_ERROR), 12, "warning: TLC exited with 12, but its output reports no error\n"
        ),
        pytest.param(RunResult(verdict=Verdict.NO_ERROR_BOUNDED), 0, "", id="0-no-error-bounded"),
        pytest.param(RunResult(verdict=Verdict.NO_ERROR), 0, "", id="0-no-error"),
        pytest.param(None, 0, "", id="raw"),
    ],
)
def test_print_run_notes_warns_when_the_code_and_the_verdict_disagree(
    result: RunResult | None, code: int, expected: str
) -> None:
    ui, out, err = _ui()
    print_run_notes(_outcome(result, code), ui)
    assert err.getvalue() == expected
    assert out.getvalue() == ""


def test_print_run_notes_says_for_a_raw_run_that_a_checkpoint_was_not_kept() -> None:
    ui, out, err = _ui()
    print_run_notes(_outcome(None, 255, dropped_checkpoint="not-asked"), ui)
    assert err.getvalue() == "a checkpoint was not kept (use --keep to keep one)\n"
    assert out.getvalue() == ""


def test_print_run_notes_leaves_a_parsed_runs_dropped_checkpoint_to_the_result_line() -> None:
    ui, out, err = _ui()
    print_run_notes(_outcome(RunResult(verdict=Verdict.INCOMPLETE), 255, dropped_checkpoint="not-asked"), ui)
    assert err.getvalue() == ""
    assert out.getvalue() == ""


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        (Verdict.NOT_CHECKED, "warning: TLC exited with 0, but its output reports that the spec was not checked\n"),
        (Verdict.INCOMPLETE, "warning: TLC exited with 0, but its output reports an incomplete run\n"),
    ],
)
def test_print_run_notes_warns_for_exit_0_with_a_spec_not_checked_or_a_run_incomplete(
    verdict: Verdict, expected: str
) -> None:
    ui, out, err = _ui()
    print_run_notes(_outcome(RunResult(verdict=verdict), 0), ui)
    assert err.getvalue() == expected
    assert out.getvalue() == ""


@pytest.mark.parametrize(
    "changes",
    [
        pytest.param({"stopped_by": "int"}, id="stopped-by-a-signal"),
        pytest.param({"stopped_for_closed_pipe": True}, id="stopped-for-a-closed-pipe"),
    ],
)
@pytest.mark.parametrize(
    ("verdict", "code"),
    [(Verdict.INCOMPLETE, 0), (Verdict.NO_ERROR, 143), (Verdict.ERRORS, 0)],
)
def test_a_run_tlaup_stopped_gets_no_disagreement_warning(changes: dict[str, Any], verdict: Verdict, code: int) -> None:
    outcome = _outcome(RunResult(verdict=verdict), code, **changes)
    assert disagreement(outcome) is None
    ui, out, err = _ui()
    print_run_notes(outcome, ui)
    assert err.getvalue() == ""
    assert out.getvalue() == ""


_IMPORTS_AFTER_A_RUN = """
import sys
sys.argv = ["tlaup", "tlc", *sys.argv[1:]]
import tlaup.cli
try:
    tlaup.cli.app(prog_name="tlaup")
except SystemExit as leaving:
    code = leaving.code
print(f"exit={code} requests={'requests' in sys.modules} truststore={'truststore' in sys.modules}", file=sys.__stderr__)
"""


@pytest.mark.parametrize("flags", [[], ["--show-command"]], ids=["run", "show-command"])
def test_a_run_with_a_build_pinned_does_not_load_the_github_client(scenario: Scenario, flags: list[str]) -> None:
    """14 F9: with a build pinned, neither a run nor --show-command imports requests or sets up truststore."""
    _set_up(scenario)
    scenario.java_replays("tlc/v1.7.4/success", 0)
    done = subprocess.run(
        [sys.executable, "-c", _IMPORTS_AFTER_A_RUN, "Slow", *flags],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    last = done.stderr.strip().splitlines()[-1]
    assert last == "exit=0 requests=False truststore=False", done.stderr
