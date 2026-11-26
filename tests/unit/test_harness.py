"""The feature harness's helpers and the steps no scenario of package 18 uses (design 01 T5, T12 rule 10).

Each step is called through its own step function, found by its text as pytest-bdd finds it, on a real
``Scenario``; the fakes are started from the test as real children (no patching, T12 rule 2).
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import typer
from pytest_bdd.steps import StepFunctionContext, step_function_context_registry

from tests.clock import FakeClock
from tests.steps import _modules
from tests.steps._process import closed_pipe, exit_code_of, run_as_process, start, start_and_signal
from tests.steps._scenario import GOLDEN_DIR, PASSTHROUGH, STARTUP_ONLY, TLAUP_JAVA_DIR, Outcome, _process_alive
from tests.steps._terminal import (
    ENTER_ALT,
    LEAVE_ALT,
    TerminalRun,
    _shows,
    ctrl_c_at_checkpoint,
    ctrl_c_once_elapsed,
    ctrl_c_once_shown,
    elapsed_seconds,
    layout_screens,
    main_screen,
    quit_once_shown,
    run_in_terminal,
    run_on_terminal,
    screen_text,
    terminal_end,
    without_escapes,
)
from tlaup.modules.registry import read_record
from tlaup.versioning.store import ToolStore

if TYPE_CHECKING:
    from tests.conftest import Isolated
    from tests.fakes.control import Fakes
    from tests.steps._scenario import Scenario

TIMEOUT = 30
POSIX_ONLY = pytest.mark.skipif(
    os.name == "nt", reason="signals and process ids as POSIX has them; no Windows CI (D15)"
)
FAILED = pytest.fail.Exception
UNIT_EXPECTED = Path(__file__).resolve().parent / "expected"


def contexts(kind: str) -> list[StepFunctionContext]:
    """The step definitions of ``tests/steps`` of one kind."""
    found = []
    for context in step_function_context_registry.values():
        if context.type == kind and context.step_func.__module__.startswith("tests.steps."):
            found.append(context)
    return found


def find_step(kind: str, text: str) -> StepFunctionContext:
    matching = [context for context in contexts(kind) if context.parser.is_matching(text)]
    assert len(matching) == 1, f"{kind} {text!r} matches {[c.step_func.__name__ for c in matching]}"
    return matching[0]


def step(scenario: Scenario, kind: str, text: str, docstring: str | None = None) -> None:
    """Run one step as pytest-bdd would: its parsed and converted arguments, the scenario, the doc string."""
    context = find_step(kind, text)
    parsed = context.parser.parse_arguments(text) or {}
    kwargs: dict[str, Any] = {key: context.converters.get(key, str)(value) for key, value in parsed.items()}
    if docstring is not None:
        kwargs["docstring"] = docstring
    context.step_func(scenario=scenario, **kwargs)


def given(scenario: Scenario, text: str, docstring: str | None = None) -> None:
    step(scenario, "given", text, docstring)


def then(scenario: Scenario, text: str) -> None:
    step(scenario, "then", text)


def script(fakes: Fakes, tool: str = "java") -> dict[str, Any]:
    data: dict[str, Any] = json.loads(Path(os.environ[f"TLAUP_FAKE_{tool.upper()}"]).read_text(encoding="utf-8"))
    return data


def run(path: Path | str, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([str(path), *args], capture_output=True, timeout=TIMEOUT, check=False, **kwargs)


def outcome(scenario: Scenario, stdout: str | None = "", stderr: str | None = "", code: int = 0) -> None:
    scenario.outcome = Outcome(exit_code=code, stdout=stdout, stderr=stderr)


def read_lines(stream: Any, count: int) -> list[bytes]:
    return [stream.readline() for _ in range(count)]


def wait_for(condition: Any, what: str) -> None:
    """Wait for a condition, never for an amount of time (T12 rule 5)."""
    deadline = time.monotonic() + TIMEOUT
    while not condition():
        if time.monotonic() >= deadline:
            pytest.fail(f"timed out waiting for {what}")
        time.sleep(0.01)


def finish(proc: subprocess.Popen[bytes]) -> int:
    try:
        return proc.wait(timeout=TIMEOUT)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        for stream in (proc.stdout, proc.stderr, proc.stdin):
            if stream is not None:
                stream.close()


# The vocabulary: each form of T5 that package 18a owns finds exactly one step, the overlapping pairs included.

GIVEN_FORMS = [
    'a spec "Violation" from the golden specs',
    'a file "{work}/a b.txt" containing:',
    "the config file contains:",
    'the folder "{work}/ro" is read-only',
    'I am in the folder "{work}/sub"',
    'java replays "tlc/v1.7.4/violation" with exit code 12',
    "java prints 100000 lines",
    'java writes "to-out" to stdout and "to-err" to stderr',
    "java echoes its input",
    "java hangs after line 40",
    "java pauses 5 ms between lines",
    'java writes "queue.chkpt, vars.chkpt" into its metadir',
    "java begins a checkpoint after line 3 and commits it before line 5",
    """java's output has "<tmp>/q01/run" replaced by "{work}\"""",
    "java ignores SIGTERM",
    "java exits with 143 on SIGTERM",
    "java is not installed",
    "java is not executable",
    'java is version "21.0.2"',
    'java is replaced by version "17.0.1"',
    "java takes 2 seconds to report its version",
    'java answers its version check with "Unable to locate a Java Runtime." on stderr and exit code 1',
    'JAVA_HOME is a JDK of version "21.0.2"',
    "JAVA_HOME is an empty folder",
    "javac is not installed",
    'javac is version "21.0.2"',
    "the editor writes:",
    "the editor exits with code 1",
    'the environment variable "TLAUP_DEBUG" is "1"',
]
THEN_FORMS = [
    "the exit code is 3",
    'stdout contains "x"',
    'stderr contains "x"',
    'stdout contains "x" 3 times',
    'stderr contains "x" 1 times',
    'stdout does not contain "x"',
    'stderr does not contain "x"',
    'stdout is exactly "x"',
    'stderr is exactly "x"',
    "stdout is empty",
    "stderr is empty",
    'stdout matches the expected file "a.txt"',
    'stderr matches the expected file "a.txt"',
    'the file "{work}/a" exists',
    'the file "{work}/a" does not exist',
    'the file "{work}/a" contains "x"',
    'the file "{work}/a" matches the expected file "a.txt"',
    "the config file is unchanged",
    "the cache holds no run folders",
    "the cache holds 1 run folder",
    "the cache holds 2 run folders",
    "the cache holds no lock files",
    "java was started 1 time",
    "javac was started 2 times",
    "git was not started",
    'the editor was started with "{config}/config.yaml"',
    'java was started without "-tool"',
    'java ran "tlc2.TLC" 1 time',
    'java ran "tlc2.TLC" 2 times',
    'java did not run "tlc2.TLC"',
    'java was started in the folder "{work}"',
    "java ran from JAVA_HOME",
    "java ran from PATH",
    'the java command matches the expected file "a.txt"',
    "the java process has exited",
    'the terminal contains "x"',
    'the terminal does not contain "x"',
    'the terminal ends with the expected file "a.txt"',
]


@pytest.mark.parametrize("text", GIVEN_FORMS)
def test_each_given_form_finds_one_step(text: str) -> None:
    find_step("given", text)


@pytest.mark.parametrize("text", THEN_FORMS)
def test_each_then_form_finds_one_step(text: str) -> None:
    find_step("then", text)


# Each When form of T5 that package 18 owns, with the one step function it must find.
WHEN_FORMS = {
    'I run "tlaup tlc Spec"': "i_run",
    'I run "tlaup tlc Spec --raw" as a process': "i_run_as_a_process",
    'I run "tlaup repl" as a process with input:': "i_run_as_a_process_with_input",
    'I run "tlaup tlc Spec" as a process whose reader closes after 1 line': "i_run_as_a_process_whose_reader_closes",
    'I run "tlaup tlc Spec" as a process whose reader closes after 2 lines': "i_run_as_a_process_whose_reader_closes",
    'I run "tlaup --help" as a process with stdout on a closed pipe': "i_run_as_a_process_with_stdout_on_a_closed_pipe",
    'I run "tlaup --nosuch" as a process with stdout and stderr on a closed pipe': (
        "i_run_as_a_process_with_both_on_a_closed_pipe"
    ),
    'I run "tlaup --nosuch" as a process with stdout on the null device and stderr on a closed pipe': (
        "i_run_as_a_process_with_stderr_on_a_closed_pipe"
    ),
    'I start "tlaup tlc Big" and send SIGTERM once java is running': "i_start_and_send_once_java_is_running",
    'I start "tlaup tlc Big" and send SIGINT to the foreground group once java is running': (
        "i_start_and_send_once_java_is_running"
    ),
    'I start "tlaup tlc Big" and send SIGINT twice': "i_start_and_send_twice",
    'I start "tlaup tlc Big" and send SIGHUP to the foreground group twice': "i_start_and_send_twice",
    'I start "tlaup tlc Spec --keep" and send SIGINT once java has begun its checkpoint': (
        "i_start_and_send_once_java_has_begun_its_checkpoint"
    ),
    'I start "tlaup tlc Spec" and send SIGINT once java has begun its checkpoint, '
    'and again once stderr contains "waiting for TLC"': "i_start_and_send_once_java_has_begun_its_checkpoint",
    'I start "tlaup tlc Spec" and send SIGTERM to the foreground group once java has begun its checkpoint': (
        "i_start_and_send_once_java_has_begun_its_checkpoint"
    ),
    'I run "tlaup tool list" in a terminal 100 by 30': "i_run_in_a_terminal",
    'I run "tlaup tool list" in a terminal 100 by 30 with stdout redirected to "out.txt"': (
        "i_run_in_a_terminal_with_a_stream_redirected"
    ),
    'I run "tlaup tool list" in a terminal 100 by 30 with stderr redirected to "{work}/err.txt"': (
        "i_run_in_a_terminal_with_a_stream_redirected"
    ),
    'I run "tlaup tool uninstall rolling" in a terminal 100 by 30 and answer "-1, 7, 2"': (
        "i_run_in_a_terminal_and_answer"
    ),
    'I start "tlaup tlc Big" in a terminal 100 by 30 and press Ctrl-C once the terminal has shown "a" and then "b"': (
        "i_start_in_a_terminal_and_press_ctrl_c_once_shown"
    ),
    'I start "tlaup tlc Spec --keep" in a terminal 100 by 30 and press Ctrl-C once java has begun its checkpoint': (
        "i_start_in_a_terminal_and_press_ctrl_c_at_the_checkpoint"
    ),
}


@pytest.mark.parametrize("text", list(WHEN_FORMS))
def test_each_when_form_finds_its_own_step(text: str) -> None:
    # find_step asserts exactly one match, so a shorter form never also matches a longer one.
    assert find_step("when", text).step_func.__name__ == WHEN_FORMS[text]


def test_the_when_forms_parse_their_arguments() -> None:
    def parsed(text: str) -> dict[str, Any]:
        return find_step("when", text).parser.parse_arguments(text) or {}

    form = 'I start "tlaup tlc Spec" and send SIGINT once java has begun its checkpoint'
    assert parsed(form) == {"command": "tlaup tlc Spec", "signal": "SIGINT", "group": None, "text": None}
    again = parsed(f'{form}, and again once stderr contains "waiting for TLC"')
    assert again["text"] == "waiting for TLC"
    group = parsed('I start "tlaup tlc Big" and send SIGINT to the foreground group twice')
    assert (group["signal"], group["group"]) == ("SIGINT", " to the foreground group")
    shown = parsed(
        'I start "tlaup x" in a terminal 80 by 24 and press Ctrl-C once the terminal has shown "a" and then "b"'
    )
    assert (shown["width"], shown["height"], shown["first"], shown["second"]) == ("80", "24", "a", "b")


def test_the_overlapping_pairs_choose_their_own_step() -> None:
    assert find_step("then", 'stdout contains "x"').step_func.__name__ == "stream_contains"
    assert find_step("then", 'stdout contains "x" 3 times').step_func.__name__ == "stream_contains_times"
    assert find_step("then", "java was started 2 times").step_func.__name__ == "tool_was_started_times"
    assert find_step("then", 'java was started with "x"').step_func.__name__ == "tool_was_started_with"
    assert find_step("then", 'java ran "tlc2.TLC" 1 time').step_func.__name__ == "java_ran_times"
    assert find_step("given", 'java writes "a" to stdout and "b" to stderr').step_func.__name__ == (
        "java_writes_to_stdout_and_stderr"
    )
    assert find_step("given", 'java writes "a, b" into its metadir').step_func.__name__ == (
        "java_writes_into_its_metadir"
    )


# The store and GitHub steps of package 29: each form finds exactly one step, with its arguments.

STORE_FORMS = {
    ("given", 'the build "v1.7.4" is installed'): ("the_build_is_installed", {"spec": "v1.7.4", "pinned": None}),
    ("given", 'the build "rolling@1a2b3c4" is installed and pinned'): (
        "the_build_is_installed",
        {"spec": "rolling@1a2b3c4", "pinned": " and pinned"},
    ),
    ("given", "no build is installed"): ("no_build_is_installed", {}),
    ("given", 'the release list is cached from "releases", 1 minutes old'): (
        "the_release_list_is_cached",
        {"recording": "releases", "minutes": "1"},
    ),
    ("given", 'the release list is cached from "releases", 1 minute old'): (
        "the_release_list_is_cached",
        {"recording": "releases", "minutes": "1"},
    ),
    ("given", 'the jar of the build "v1.7.4" is truncated'): ("the_jar_of_the_build_is_truncated", {"spec": "v1.7.4"}),
    ("given", 'GitHub answers from "releases"'): ("github_answers_from", {"recording": "releases"}),
    ("given", 'GitHub answers 404 to "/releases/tags/v1.7.4"'): (
        "github_answers_status_to",
        {"status": "404", "path": "/releases/tags/v1.7.4"},
    ),
    ("given", "GitHub is unreachable"): ("github_is_unreachable", {}),
    ("then", 'the pinned build is "v1.7.4"'): ("the_pinned_build_is", {"spec": "v1.7.4"}),
    ("then", "no build is pinned"): ("no_build_is_pinned", {}),
    ("then", "the installed builds are:"): ("the_installed_builds_are", {}),
    ("then", "1 request was sent to GitHub"): ("requests_were_sent_to_github", {"count": "1"}),
    ("then", "2 requests were sent to GitHub"): ("requests_were_sent_to_github", {"count": "2"}),
    ("then", "1 request(s) were sent to GitHub"): ("requests_were_sent_to_github", {"count": "1"}),
    ("then", "0 jar downloads were made"): ("jar_downloads_were_made", {"count": "0"}),
    ("then", "1 jar download was made"): ("jar_downloads_were_made", {"count": "1"}),
    ("then", "1 jar download(s) were made"): ("jar_downloads_were_made", {"count": "1"}),
    ("then", 'no request carried a token to "api.github.com"'): (
        "no_request_carried_a_token_to",
        {"host": "api.github.com"},
    ),
}


@pytest.mark.parametrize(("kind", "text"), list(STORE_FORMS))
def test_each_store_and_github_form_finds_one_step(kind: str, text: str) -> None:
    name, arguments = STORE_FORMS[(kind, text)]
    context = find_step(kind, text)
    assert context.step_func.__name__ == name
    assert (context.parser.parse_arguments(text) or {}) == arguments


def test_the_store_forms_do_not_take_each_others_text() -> None:
    # The pairs that share words: "installed" and "installed and pinned", the build and its jar, the pin and
    # "no build", the two GitHub answers.
    assert find_step("given", 'the build "v1.7.4" is installed and pinned').step_func.__name__ == (
        "the_build_is_installed"
    )
    assert find_step("given", 'the jar of the build "v1.7.4" is truncated').step_func.__name__ == (
        "the_jar_of_the_build_is_truncated"
    )
    assert find_step("then", "no build is pinned").step_func.__name__ == "no_build_is_pinned"
    assert find_step("given", 'GitHub answers 500 to "https://github.com/x"').step_func.__name__ == (
        "github_answers_status_to"
    )
    for text in ('the build "a" is installed and', 'the build "a" is pinned', "GitHub answers 404"):
        assert not [c for c in contexts("given") if c.parser.is_matching(text)], text


# The module steps of package 31, tried against the forms that share their words.

MODULE_FORMS = {
    ("given", 'the module "Queue" is registered'): ("the_module_is_registered", {"name": "Queue"}),
    ("given", 'a module source "Queue" from the fake sources'): (
        "a_module_source_from_the_fake_sources",
        {"name": "Queue"},
    ),
    ("given", 'javac fails with "syntax-error"'): ("javac_fails_with", {"recording": "syntax-error"}),
    ("then", "the registered modules are:"): ("the_registered_modules_are", {}),
}


@pytest.mark.parametrize(("kind", "text"), list(MODULE_FORMS))
def test_each_module_form_finds_one_step(kind: str, text: str) -> None:
    name, arguments = MODULE_FORMS[(kind, text)]
    context = find_step(kind, text)
    assert context.step_func.__name__ == name
    assert (context.parser.parse_arguments(text) or {}) == arguments


def test_the_module_forms_do_not_take_each_others_text() -> None:
    # The pairs that share words: "a ... from the ..." forms, "the ... is ..." forms, the two javac forms and
    # the two tables.
    assert find_step("given", 'javac is version "25.0.5"').step_func.__name__ == "javac_is_version"
    assert find_step("given", "javac is not installed").step_func.__name__ == "javac_is_not_installed"
    assert find_step("given", 'a spec "Queue" from the golden specs').step_func.__name__ == (
        "a_spec_from_the_golden_specs"
    )
    assert find_step("given", 'the build "v1.7.4" is installed and pinned').step_func.__name__ == (
        "the_build_is_installed"
    )
    assert find_step("then", "the installed builds are:").step_func.__name__ == "the_installed_builds_are"
    for text in (
        'the module "Queue" is installed',
        'a module source "Queue" from the golden specs',
        'a spec "Queue" from the fake sources',
        'javac fails with ""',
        "the registered modules are",
    ):
        assert not [c for c in contexts("given") + contexts("then") if c.parser.is_matching(text)], text


def test_steps_owned_by_later_packages_are_not_here() -> None:
    for kind, text in [
        ("when", 'I start "tlaup tlc Big" in a terminal 100 by 30 and press Ctrl-\\ once java is running'),
    ]:
        assert not [c for c in contexts(kind) if c.parser.is_matching(text)], text


# The screen steps of package 40, tried against the terminal forms that share their words.

LAYOUT_FORMS = {
    ("then", "the terminal showed the layout"): ("the_terminal_showed_the_layout", {}),
    ("then", 'the last layout frame contains "Finished"'): ("the_last_layout_frame_contains", {"text": "Finished"}),
    ("then", "the terminal stayed on the main screen"): ("the_terminal_stayed_on_the_main_screen", {}),
    (
        "when",
        'I start "tlaup tlc Big --refresh-interval 0.2" in a terminal 100 by 30 and press Ctrl-C once the terminal '
        'has shown "Checking" and then an elapsed time 2 seconds later',
    ): (
        "i_start_in_a_terminal_and_press_ctrl_c_once_elapsed",
        {
            "command": "tlaup tlc Big --refresh-interval 0.2",
            "width": "100",
            "height": "30",
            "first": "Checking",
            "seconds": "2",
        },
    ),
}


@pytest.mark.parametrize(("kind", "text"), list(LAYOUT_FORMS))
def test_each_layout_form_finds_one_step(kind: str, text: str) -> None:
    name, arguments = LAYOUT_FORMS[(kind, text)]
    context = find_step(kind, text)
    assert context.step_func.__name__ == name
    assert (context.parser.parse_arguments(text) or {}) == arguments


def test_the_layout_forms_do_not_take_each_others_text() -> None:
    # The pairs that share words: the two Ctrl-C forms ending "and then", "contains" on the terminal and on the
    # last frame, the two "the terminal ..." forms.
    shown = 'I start "tlaup x" in a terminal 80 by 24 and press Ctrl-C once the terminal has shown "a" and then "b"'
    assert find_step("when", shown).step_func.__name__ == "i_start_in_a_terminal_and_press_ctrl_c_once_shown"
    assert find_step("then", 'the terminal contains "Finished"').step_func.__name__ == "the_terminal_contains"
    assert find_step("then", 'the terminal ends with the expected file "a.txt"').step_func.__name__ == (
        "the_terminal_ends_with_the_expected_file"
    )
    for kind, text in (
        (
            "when",
            'I start "tlaup x" in a terminal 80 by 24 and press Ctrl-C once the terminal has shown "a" and then '
            '"an elapsed time 2 seconds later"',
        ),
    ):
        assert find_step(kind, text).step_func.__name__ == "i_start_in_a_terminal_and_press_ctrl_c_once_shown"
    for text in ("the terminal showed the layout twice", 'the last layout frame contains "x" 2 times'):
        assert not [c for c in contexts("then") if c.parser.is_matching(text)], text


# Placeholders


def test_each_placeholder_expands_to_its_folder(scenario: Scenario, isolated: Isolated) -> None:
    paths = isolated.paths
    assert scenario.expand("{home}") == str(isolated.home)
    assert scenario.expand("{work}/x") == f"{isolated.work}/x"
    assert scenario.expand("{tools}") == str(paths.tools)
    assert scenario.expand("{modules}") == str(paths.modules)
    assert scenario.expand("{runs}") == str(paths.runs)
    assert scenario.expand("{config}") == str(paths.config)


def make_run_folder(scenario: Scenario, name: str, *, kept: bool) -> Path:
    folder = scenario.paths().runs / name
    folder.mkdir(parents=True)
    (folder / "run.json").write_text(json.dumps({"kept": kept}), encoding="utf-8")
    return folder


def test_kept_is_the_one_kept_run_folder(scenario: Scenario) -> None:
    make_run_folder(scenario, "20261115T100000Z-00000001", kept=False)
    kept = make_run_folder(scenario, "20261115T100000Z-00000002", kept=True)
    assert scenario.expand("{kept}/queue.chkpt") == f"{kept}/queue.chkpt"


def test_kept_id_is_the_run_id_alone(scenario: Scenario) -> None:
    make_run_folder(scenario, "20261115T100000Z-00000001", kept=False)
    make_run_folder(scenario, "20261115T100000Z-00000002", kept=True)
    assert scenario.expand("tlaup cache clean {kept-id}") == "tlaup cache clean 20261115T100000Z-00000002"


@pytest.mark.parametrize("kept", [0, 2])
def test_kept_id_fails_as_kept_does(scenario: Scenario, kept: int) -> None:
    make_run_folder(scenario, "20261115T100000Z-00000001", kept=False)
    for number in range(kept):
        make_run_folder(scenario, f"20261115T100000Z-0000001{number}", kept=True)
    with pytest.raises(FAILED, match="exactly one kept run folder"):
        scenario.expand("{kept-id}")


def test_kept_with_no_kept_folder_fails(scenario: Scenario) -> None:
    make_run_folder(scenario, "20261115T100000Z-00000001", kept=False)
    with pytest.raises(FAILED, match=r"exactly one kept run folder.*found 0"):
        scenario.expand("{kept}")


def test_kept_with_two_kept_folders_fails(scenario: Scenario) -> None:
    make_run_folder(scenario, "20261115T100000Z-00000001", kept=True)
    make_run_folder(scenario, "20261115T100000Z-00000002", kept=True)
    with pytest.raises(FAILED, match="found 2"):
        scenario.expand("{kept}")


def test_other_braces_are_left_alone(scenario: Scenario) -> None:
    assert scenario.expand("{a: 1, b: {kept-ids}} {}") == "{a: 1, b: {kept-ids}} {}"


def test_a_placeholder_holding_a_space_stays_one_word(scenario: Scenario, tmp_path: Path) -> None:
    given(scenario, f'the environment variable "TLAUP_HOME" is "{tmp_path}/with space"')
    assert scenario.words("tlaup tlc {tools}/x 'a b'") == ["tlaup", "tlc", f"{tmp_path}/with space/cache/tool/x", "a b"]


def test_a_command_must_start_with_tlaup(scenario: Scenario) -> None:
    with pytest.raises(FAILED, match='starts with "tlaup"'):
        scenario.words("python -m tlaup")


def test_placeholders_expand_in_doc_strings(scenario: Scenario, isolated: Isolated) -> None:
    given(scenario, 'a file "{work}/a b/notes.txt" containing:', "home: {home}\nflow: {a: 1}")
    text = (isolated.work / "a b" / "notes.txt").read_text(encoding="utf-8")
    assert text == f"home: {isolated.home}\nflow: {{a: 1}}"


# Rule 10's two refusals


@pytest.mark.parametrize("name", ["PYTHONIOENCODING", "LC_ALL"])
def test_a_startup_only_variable_refuses_the_in_process_step(scenario: Scenario, name: str) -> None:
    given(scenario, f'the environment variable "{name}" is "utf-8"')
    with pytest.raises(FAILED, match='use "as a process"'):
        step(scenario, "when", 'I run "tlaup --help"')


def test_startup_only_names() -> None:
    assert STARTUP_ONLY("PYTHONPATH")
    assert STARTUP_ONLY("LANG")
    assert STARTUP_ONLY("LC_CTYPE")
    assert not STARTUP_ONLY("TLAUP_HOME")


def group_app() -> typer.Typer:
    """A plain Typer group, without tlaup's TlaupGroup, for commands the tests add."""
    app = typer.Typer(add_completion=False)

    @app.callback()
    def root() -> None:
        """A group, so the command is named on the command line."""

    return app


def passthrough_app(java: Path, out: Path) -> typer.Typer:
    """An app whose command starts the fake java with its stdout on a file, as run_passthrough would."""
    app = group_app()

    @app.command()
    def start() -> None:
        with out.open("wb") as handle:
            subprocess.run([str(java), "tlc2.TLC"], stdout=handle, timeout=TIMEOUT, check=False)

    return app


def test_a_java_start_without_a_pipe_refuses_the_in_process_step(scenario: Scenario, tmp_path: Path) -> None:
    given(scenario, "java prints 1 lines")
    app = passthrough_app(scenario.fakes.bin / "java", tmp_path / "out.txt")
    with pytest.raises(FAILED) as failure:
        scenario.run_in_process("tlaup start", app=app)
    assert PASSTHROUGH in str(failure.value)
    assert scenario.fakes.log("java")[0]["stdout_pipe"] is False


def test_an_exception_past_the_mapping_fails_with_its_traceback(scenario: Scenario) -> None:
    app = group_app()  # no TlaupGroup: nothing maps the error

    @app.command()
    def boom() -> None:
        message = "past the mapping"
        raise RuntimeError(message)

    with pytest.raises(FAILED, match=r"(?s)raised past the error mapping.*Traceback.*RuntimeError: past the mapping"):
        scenario.run_in_process("tlaup boom", app=app)


def test_before_run_hooks_run_before_each_call(scenario: Scenario) -> None:
    calls: list[str] = []
    scenario.before_run.append(lambda: calls.append("hook"))
    scenario.run_in_process("tlaup --help")
    scenario.run_in_process("tlaup --help")
    assert calls == ["hook", "hook"]


# Declaring runs


@POSIX_ONLY
def test_a_declared_run_with_three_changes_is_one_run(scenario: Scenario, fakes: Fakes, tmp_path: Path) -> None:
    given(scenario, 'java replays "tlc/v1.7.4/violation" with exit code 12')
    given(scenario, "java hangs after line 40")
    given(scenario, 'java writes "queue.chkpt, vars.chkpt" into its metadir')
    runs = script(fakes)["runs"]
    assert len(runs) == 1
    assert runs[0]["main"] == "tlc2.TLC"
    assert runs[0]["stdout"] == "tlc/v1.7.4/violation.out"
    assert (runs[0]["exit"], runs[0]["hang_after_line"]) == (12, 40)
    assert runs[0]["write_into_metadir"] == ["queue.chkpt", "vars.chkpt"]
    metadir = tmp_path / "meta"
    proc = subprocess.Popen(
        [str(fakes.bin / "java"), "tlc2.TLC", "-metadir", str(metadir)], stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        assert proc.stdout is not None
        got = b"".join(read_lines(proc.stdout, 40))
        golden = (GOLDEN_DIR / "tlc/v1.7.4/violation.out").read_bytes()
        assert got == b"".join(golden.splitlines(keepends=True)[:40])
        proc.send_signal(signal.SIGTERM)
        assert finish(proc) == 143
    finally:
        finish(proc)
    (folder,) = metadir.iterdir()
    assert sorted(p.name for p in folder.iterdir()) == ["queue.chkpt", "vars.chkpt"]


def test_a_case_with_a_stderr_key_replays_its_err_file(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, 'java replays "tlc/v1.7.4/tool-missing-module" with exit code 150')
    given(scenario, 'java replays "sany/v1.7.4/sany-parseerr" with exit code 255')
    first, second = script(fakes)["runs"]
    assert first["stderr"] == "tlc/v1.7.4/tool-missing-module.err"
    assert (second["main"], second["stderr"]) == ("tla2sany.SANY", None)
    result = run(fakes.bin / "java", "tlc2.TLC")
    assert result.stderr == (GOLDEN_DIR / "tlc/v1.7.4/tool-missing-module.err").read_bytes()
    assert result.returncode == 150


def test_an_unknown_case_fails(scenario: Scenario) -> None:
    with pytest.raises(FAILED, match="no golden case"):
        given(scenario, 'java replays "tlc/v1.7.4/nosuch" with exit code 0')


@pytest.mark.parametrize(
    "text",
    [
        "java hangs after line 40",
        "java pauses 5 ms between lines",
        'java writes "queue.chkpt" into its metadir',
        "java begins a checkpoint after line 3 and commits it before line 5",
        """java's output has "<tmp>" replaced by "{work}\"""",
        "java ignores SIGINT",
        "java exits with 1 on SIGTERM",
    ],
)
def test_a_change_with_no_declared_run_fails(scenario: Scenario, text: str) -> None:
    with pytest.raises(FAILED, match="no run of java is declared yet"):
        given(scenario, text)


def test_a_signal_the_fake_has_no_field_for_fails(scenario: Scenario) -> None:
    given(scenario, "java prints 1 lines")
    with pytest.raises(FAILED, match="SIGINT or SIGTERM only"):
        given(scenario, "java ignores SIGHUP")


def test_the_signal_changes_set_their_fields(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, "java prints 1 lines")
    given(scenario, "java ignores SIGTERM")
    given(scenario, "java exits with 3 on SIGINT")
    given(scenario, "java pauses 5 ms between lines")
    (only,) = script(fakes)["runs"]
    assert (only["on_sigterm"], only["on_sigint"], only["line_delay_ms"]) == ("ignore", 3, 5)


def test_java_prints_writes_and_echoes(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, "java prints 3 lines")
    given(scenario, 'java writes "a" to stdout and "b" to stderr')
    given(scenario, "java echoes its input")
    printed = run(fakes.bin / "java", "tlc2.TLC")
    assert (printed.stdout, printed.returncode) == (b"line 1\nline 2\nline 3\n", 0)
    written = run(fakes.bin / "java", "tlc2.TLC")
    assert (written.stdout, written.stderr, written.returncode) == (b"a\n", b"b\n", 0)
    echoed = run(fakes.bin / "java", "tlc2.REPL", input=b"1 + 1\nx\n")
    assert (echoed.stdout, echoed.returncode) == (b"1 + 1\nx\n", 0)


# Which Java there is


def test_java_is_version(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, 'java is version "21.0.2"')
    result = run(fakes.bin / "java", "-version")
    assert b'openjdk version "21.0.2"' in result.stderr
    assert result.returncode == 0


def test_java_answers_its_version_check(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, 'java answers its version check with "Unable to locate a Java Runtime." on stderr and exit code 1')
    result = run(fakes.bin / "java", "-version")
    assert (result.stdout, result.stderr, result.returncode) == (b"", b"Unable to locate a Java Runtime.\n", 1)


def test_java_answers_its_version_check_on_stdout(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, 'java answers its version check with "not a version" on stdout and exit code 0')
    result = run(fakes.bin / "java", "-version")
    assert (result.stdout, result.stderr, result.returncode) == (b"not a version\n", b"", 0)


def test_java_takes_seconds_to_report_its_version(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, "java takes 2 seconds to report its version")
    assert script(fakes)["version_delay_ms"] == 2000


def test_java_is_replaced_by_version(scenario: Scenario, fakes: Fakes) -> None:
    launcher = fakes.bin / "java"
    before = launcher.stat()
    given(scenario, 'java is replaced by version "17.0.1"')
    after = launcher.stat()
    assert (after.st_size, after.st_ino) != (before.st_size, before.st_ino)
    assert b'openjdk version "17.0.1"' in run(launcher, "-version").stderr


def test_javac_is_version(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, 'javac is version "21.0.2"')
    result = run(fakes.bin / "javac", "-version")
    assert (result.stdout, result.returncode) == (b"javac 21.0.2\n", 0)


@pytest.mark.parametrize(
    ("text", "tool"),
    [("java is not installed", "java"), ("java is not executable", "java"), ("javac is not installed", "javac")],
)
def test_a_missing_or_unusable_launcher_is_not_found(scenario: Scenario, text: str, tool: str) -> None:
    assert shutil.which(tool, path=os.environ["PATH"]) is not None
    given(scenario, text)
    assert shutil.which(tool, path=os.environ["PATH"]) is None


def test_java_home_is_a_jdk(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, 'JAVA_HOME is a JDK of version "21.0.2"')
    given(scenario, "java prints 2 lines")  # declared after the JDK, and still its java's run
    java_home = Path(os.environ["JAVA_HOME"])
    assert b'openjdk version "21.0.2"' in run(java_home / "bin" / "java", "-version").stderr
    assert run(java_home / "bin" / "javac", "-version").stdout == b"javac 21.0.2\n"
    assert run(java_home / "bin" / "java", "tlc2.TLC").stdout == b"line 1\nline 2\n"
    assert b'openjdk version "25.0.5"' in run(fakes.bin / "java", "-version").stderr


def test_java_home_is_an_empty_folder(scenario: Scenario) -> None:
    given(scenario, "JAVA_HOME is an empty folder")
    java_home = Path(os.environ["JAVA_HOME"])
    assert java_home.is_dir()
    assert list(java_home.iterdir()) == []


# The checkpoint and replace changes


@POSIX_ONLY
def test_the_checkpoint_change(scenario: Scenario, fakes: Fakes, tmp_path: Path) -> None:
    for _ in range(2):  # each declared run answers one start
        given(scenario, 'java replays "tlc/v1.7.4/violation" with exit code 12')
        given(scenario, "java begins a checkpoint after line 3 and commits it before line 5")
        given(scenario, "java hangs after line 5")
        given(scenario, "java exits with 143 on SIGTERM")
    first, second = (run["checkpoint"] for run in script(fakes)["runs"])
    assert (first["begin_after_line"], first["commit_before_line"]) == (3, 5)
    releases = [Path(first["release_file"]), Path(second["release_file"])]
    assert releases[0] != releases[1]
    for release in releases:
        assert release.is_relative_to(scenario.folder)
        assert not release.exists()

    def start(metadir: Path) -> subprocess.Popen[bytes]:
        java = [str(fakes.bin / "java"), "tlc2.TLC", "-metadir", str(metadir)]
        return subprocess.Popen(java, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def wait_checkpoint(count: int) -> Path:
        def lines() -> list[dict[str, Any]]:
            return [line for line in fakes.log("java") if line["event"] == "checkpoint"]

        wait_for(lambda: len(lines()) == count, f"checkpoint line {count}")
        return Path(lines()[-1]["folder"])

    proc = start(tmp_path / "meta1")
    try:
        assert proc.stdout is not None
        read_lines(proc.stdout, 3)
        folder = wait_checkpoint(1)
        assert sorted(p.name for p in folder.iterdir()) == ["queue.tmp", "vars.tmp"]
        proc.send_signal(signal.SIGTERM)
        assert finish(proc) == 143
        assert sorted(p.name for p in folder.iterdir()) == ["queue.tmp", "vars.tmp"]
    finally:
        finish(proc)
    proc = start(tmp_path / "meta2")
    try:
        assert proc.stdout is not None
        read_lines(proc.stdout, 3)
        folder = wait_checkpoint(2)
        releases[1].touch()
        read_lines(proc.stdout, 2)  # line 5 comes only after the rename
        assert sorted(p.name for p in folder.iterdir()) == ["queue.chkpt", "vars.chkpt"]
        assert proc.poll() is None  # it hangs after line 5
        proc.send_signal(signal.SIGTERM)
        assert finish(proc) == 143
    finally:
        finish(proc)


def test_the_replace_change(scenario: Scenario, fakes: Fakes, isolated: Isolated) -> None:
    given(scenario, 'java replays "tlc/v1.7.4/success" with exit code 0')
    given(scenario, """java's output has "<tmp>/q01/run" replaced by "{work}\"""")
    (only,) = script(fakes)["runs"]
    assert only["replace"] == {"<tmp>/q01/run": str(isolated.work)}
    result = run(fakes.bin / "java", "tlc2.TLC")
    assert f"Parsing file {isolated.work}/Success.tla\n".encode() in result.stdout
    assert b"<tmp>" not in result.stdout


# Files, the config file, the editor, the environment


def test_a_spec_from_the_golden_specs(scenario: Scenario, isolated: Isolated) -> None:
    given(scenario, 'a spec "Violation" from the golden specs')
    given(scenario, 'a spec "Good" from the golden specs')  # no .cfg
    assert sorted(p.name for p in isolated.work.iterdir()) == ["Good.tla", "Violation.cfg", "Violation.tla"]
    with pytest.raises(FAILED, match="no golden spec"):
        given(scenario, 'a spec "Nosuch" from the golden specs')


def test_the_config_file_is_unchanged(scenario: Scenario, isolated: Isolated) -> None:
    with pytest.raises(FAILED, match="needs"):
        then(scenario, "the config file is unchanged")
    given(scenario, "the config file contains:", "tlc:\n  workers: {home}")
    config = isolated.paths.config_file
    assert config.read_text(encoding="utf-8") == f"tlc:\n  workers: {isolated.home}"
    then(scenario, "the config file is unchanged")
    config.write_text("tlc: {}\n", encoding="utf-8")
    with pytest.raises(FAILED, match="changed"):
        then(scenario, "the config file is unchanged")


def test_the_editor_steps(scenario: Scenario, fakes: Fakes, tmp_path: Path) -> None:
    given(scenario, "the editor writes:", "key: {work}")
    given(scenario, "the editor exits with code 3")
    target = tmp_path / "edited.yaml"
    result = run(fakes.bin / "editor", str(target))
    assert result.returncode == 3
    assert target.read_text(encoding="utf-8") == f"key: {scenario.isolated.work}"


@POSIX_ONLY
def test_the_folder_is_read_only_until_the_end(scenario: Scenario, isolated: Isolated) -> None:
    if os.geteuid() == 0:
        pytest.skip("permissions do not bind as root")
    given(scenario, 'the folder "ro" is read-only')
    folder = isolated.work / "ro"
    assert not os.access(folder, os.W_OK)
    scenario.cleanup()
    assert os.access(folder, os.W_OK)


def test_the_folder_of_an_installed_build_is_found_through_the_store(scenario: Scenario, isolated: Isolated) -> None:
    if os.geteuid() == 0:
        pytest.skip("permissions do not bind as root")
    given(scenario, 'the build "v1.7.4" is installed')
    (build,) = ToolStore(isolated.paths, now=FakeClock().now).builds()
    given(scenario, 'the folder "{tools}/v1.7.4@5a47802" is read-only')
    assert not os.access(build.path, os.W_OK)
    assert not (isolated.paths.tools / "v1.7.4@5a47802").exists()
    given(scenario, 'the folder "{tools}/nosuch" is read-only')  # names no build: the folder as written
    assert not os.access(isolated.paths.tools / "nosuch", os.W_OK)
    scenario.cleanup()
    assert os.access(build.path, os.W_OK)


def test_i_am_in_the_folder(scenario: Scenario, isolated: Isolated) -> None:
    given(scenario, 'I am in the folder "{work}/a/b"')
    assert Path.cwd() == isolated.work / "a" / "b"
    given(scenario, 'a file "x.txt" containing:', "x")
    assert (isolated.work / "a" / "b" / "x.txt").is_file()


def test_an_empty_variable_is_set_empty(scenario: Scenario) -> None:
    given(scenario, 'the environment variable "TLAUP_X" is ""')
    assert os.environ["TLAUP_X"] == ""
    assert scenario.env_set == {"TLAUP_X": ""}


# The result steps


def test_the_result_steps(scenario: Scenario) -> None:
    outcome(scenario, stdout="a x b x c\n", stderr="", code=3)
    then(scenario, "the exit code is 3")
    then(scenario, 'stdout contains "x b"')
    then(scenario, 'stdout contains "x" 2 times')
    then(scenario, 'stdout does not contain "y"')
    then(scenario, 'stdout is exactly "a x b x c"')
    then(scenario, "stderr is empty")
    for text in [
        "the exit code is 0",
        'stdout contains "y"',
        'stdout contains "x" 1 times',
        'stdout does not contain "x"',
        'stdout is exactly "a x b x"',
        "stdout is empty",
    ]:
        with pytest.raises(FAILED):
            then(scenario, text)


def test_counting_does_not_overlap(scenario: Scenario) -> None:
    outcome(scenario, stdout="aaaa")
    then(scenario, 'stdout contains "aa" 2 times')


def test_a_closed_stream_cannot_be_read(scenario: Scenario) -> None:
    outcome(scenario, stdout=None, stderr=None, code=141)
    then(scenario, "the exit code is 141")
    for text in ['stdout contains "x"', "stderr is empty", 'stdout does not contain "x"']:
        with pytest.raises(FAILED, match="closed pipe or the null device"):
            then(scenario, text)


def test_a_result_step_before_a_run_fails(scenario: Scenario) -> None:
    with pytest.raises(FAILED, match="no command has run yet"):
        then(scenario, "the exit code is 0")


def test_stream_matches_the_expected_file(scenario: Scenario) -> None:
    scenario.expected_dir = UNIT_EXPECTED
    outcome(scenario, stdout="one\ntwo\n")
    then(scenario, 'stdout matches the expected file "harness/two-lines.txt"')
    outcome(scenario, stdout="one\n")
    with pytest.raises(FAILED, match="differs"):
        then(scenario, 'stdout matches the expected file "harness/two-lines.txt"')


def test_the_file_steps(scenario: Scenario, isolated: Isolated) -> None:
    scenario.expected_dir = UNIT_EXPECTED
    (isolated.work / "out.txt").write_text("one\ntwo\n", encoding="utf-8")
    then(scenario, 'the file "{work}/out.txt" exists')
    then(scenario, 'the file "out.txt" contains "two"')
    then(scenario, 'the file "out.txt" matches the expected file "harness/two-lines.txt"')
    then(scenario, 'the file "nosuch" does not exist')
    with pytest.raises(FAILED):
        then(scenario, 'the file "nosuch" exists')
    with pytest.raises(FAILED):
        then(scenario, 'the file "out.txt" contains "three"')


def test_the_run_folder_steps(scenario: Scenario) -> None:
    then(scenario, "the cache holds no run folders")
    then(scenario, "the cache holds no lock files")
    make_run_folder(scenario, "20261115T100000Z-00000001", kept=False)
    then(scenario, "the cache holds 1 run folder")
    (scenario.paths().runs / "20261115T100000Z-00000001.lock").write_bytes(b"")
    then(scenario, "the cache holds 1 run folder")
    with pytest.raises(FAILED, match="lock files"):
        then(scenario, "the cache holds no lock files")
    with pytest.raises(FAILED):
        then(scenario, "the cache holds no run folders")


# The fakes' Then steps, on logs the test makes by starting the fakes itself


def test_starts_count_the_version_check(scenario: Scenario, fakes: Fakes) -> None:
    then(scenario, "java was not started")
    given(scenario, "java prints 1 lines")
    run(fakes.bin / "java", "-version")
    run(fakes.bin / "java", "-Dx=1", "tlc2.TLC", "-tool")
    then(scenario, "java was started 2 times")
    then(scenario, 'java ran "tlc2.TLC" 1 time')
    then(scenario, 'java did not run "tla2sany.SANY"')
    then(scenario, 'java was started with "-tool"')
    then(scenario, 'java was started without "-workers"')
    then(scenario, "javac was not started")
    with pytest.raises(FAILED):
        then(scenario, 'java was started without "-tool"')
    with pytest.raises(FAILED):
        then(scenario, 'java ran "tlc2.TLC" 2 times')


def test_the_editor_and_git_are_counted(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, "the editor exits with code 0")
    run(fakes.bin / "editor", str(scenario.paths().config_file))
    then(scenario, "the editor was started 1 time")
    then(scenario, 'the editor was started with "{config}/config.yaml"')
    then(scenario, "git was not started")


def test_where_java_ran_from(scenario: Scenario, fakes: Fakes, isolated: Isolated) -> None:
    given(scenario, 'JAVA_HOME is a JDK of version "21.0.2"')
    given(scenario, "java prints 1 lines")
    given(scenario, "java prints 1 lines")
    sub = isolated.work / "sub"
    sub.mkdir()
    run(Path(os.environ["JAVA_HOME"]) / "bin" / "java", "tlc2.TLC", cwd=sub)
    then(scenario, "java ran from JAVA_HOME")
    then(scenario, 'java was started in the folder "{work}/sub"')
    with pytest.raises(FAILED):
        then(scenario, "java ran from PATH")
    run(fakes.bin / "java", "tlc2.TLC")
    then(scenario, "java ran from PATH")
    then(scenario, 'java was started in the folder "{work}"')


def test_the_agent_folder_is_the_installed_packages_java_folder() -> None:
    assert (TLAUP_JAVA_DIR / "lifeline.jar").is_file()


def test_the_java_command_matches_the_expected_file(scenario: Scenario, fakes: Fakes, isolated: Isolated) -> None:
    scenario.expected_dir = UNIT_EXPECTED
    paths = isolated.paths
    given(scenario, "java prints 1 lines")
    run_id = "20261115T100000Z-3fa9c1d2"
    args = [
        f"-javaagent:{TLAUP_JAVA_DIR / 'lifeline.jar'}=pid=4242",
        "-cp",
        f"{paths.tools}/v1.7.4/tla2tools.jar",
        "tlc2.TLC",
        "-metadir",
        str(paths.runs / run_id),
        "-userFile",
        f"{paths.runs / run_id}/user.txt",
        f"{isolated.work}/Spec.tla",
        f"{isolated.home}/other",
    ]
    run(fakes.bin / "java", "-version")
    run(fakes.bin / "java", *args)
    then(scenario, 'the java command matches the expected file "harness/java-command.txt"')


@POSIX_ONLY
def test_the_java_process_has_exited_waits_for_an_orphan(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, "java echoes its input")
    read_end, write_end = os.pipe()
    # A parent that starts the fake with its stdin on the pipe and exits at once, leaving it orphaned.
    parent = f"import subprocess, sys; subprocess.Popen([{str(fakes.bin / 'java')!r}, 'tlc2.REPL'], stdin={read_end})"
    subprocess.run([sys.executable, "-c", parent], pass_fds=(read_end,), timeout=TIMEOUT, check=True)
    os.close(read_end)
    wait_for(lambda: scenario.starts("java"), "the fake's start line")
    with pytest.raises(FAILED, match="still running"):
        scenario.check_java_exited(timeout=0.1)
    os.close(write_end)  # end of input: the fake ends
    then(scenario, "the java process has exited")


# The real-process runner (package 18b), with small programs as argv


def py(code: str, *args: str | Path) -> list[str]:
    return [sys.executable, "-c", code, *(str(arg) for arg in args)]


@pytest.fixture
def reap(fakes: Fakes) -> Any:
    """Kill, by process id, any fake java a test leaves running (a failing test must not leak one)."""
    yield
    for line in fakes.log("java"):
        if line.get("event") == "start" and _process_alive(int(line["pid"])):
            with contextlib.suppress(ProcessLookupError):  # it may exit between the check and the kill
                os.kill(int(line["pid"]), signal.SIGKILL)


def test_exit_code_of() -> None:
    assert exit_code_of(-15) == 143
    assert exit_code_of(-2) == 130
    assert exit_code_of(3) == 3


def test_a_write_to_a_closed_pipe_fails_in_the_child() -> None:
    write_end = closed_pipe()
    code = "import os\ntry:\n    os.write(1, b'x')\nexcept BrokenPipeError:\n    os._exit(7)\n"
    try:
        child = start(py(code), stdin=subprocess.DEVNULL, stdout=write_end, stderr=subprocess.DEVNULL)
    finally:
        os.close(write_end)
    assert child.wait(timeout=TIMEOUT) == 7


def test_the_captured_streams_and_the_null_stdin(scenario: Scenario) -> None:
    code = "import sys; print('out'); print('err', file=sys.stderr); print(repr(sys.stdin.read()))"
    result = run_as_process(scenario, py(code))
    assert (result.exit_code, result.stdout, result.stderr) == (0, "out\n''\n", "err\n")
    assert result.pid is not None


def test_the_input_form_writes_the_doc_string_and_closes(scenario: Scenario, isolated: Isolated) -> None:
    result = run_as_process(scenario, py("import sys; sys.stdout.write(sys.stdin.read())"), "input", text="a\n{work}\n")
    assert result.stdout == f"a\n{isolated.work}\n"


@POSIX_ONLY
def test_a_child_killed_by_sigterm_reports_143(scenario: Scenario) -> None:
    result = run_as_process(scenario, py("import os, signal; os.kill(os.getpid(), signal.SIGTERM)"))
    assert result.exit_code == 143


def test_the_reader_closes_after_one_line_of_a_long_output(scenario: Scenario) -> None:
    result = run_as_process(scenario, py("for i in range(100_000): print(i)"), "reader", lines=1)
    assert result.stdout == "0\n"
    assert result.exit_code != 0  # ended by the closed pipe, not by printing everything


def test_the_closed_pipe_forms_cannot_be_read(scenario: Scenario) -> None:
    code = "import sys; print('x'); print('y', file=sys.stderr)"
    for arrangement, readable in [("closed-stdout", (False, True)), ("closed-both", (False, False))]:
        result = run_as_process(scenario, py(code), arrangement)
        assert (result.stdout is not None, result.stderr is not None) == readable, arrangement
    result = run_as_process(scenario, py(code), "null-and-closed")
    assert (result.stdout, result.stderr) == (None, None)


def test_the_closed_pipe_steps_on_tlaup(scenario: Scenario) -> None:
    step(scenario, "when", 'I run "tlaup --nosuch" as a process with stdout and stderr on a closed pipe')
    then(scenario, "the exit code is 141")
    with pytest.raises(FAILED, match="closed pipe"):
        then(scenario, 'stderr does not contain "Traceback"')


def test_a_process_that_outlives_its_wait_is_killed_and_shows_its_output(scenario: Scenario) -> None:
    code = "import sys, time; print('hello', flush=True); time.sleep(60)"
    with pytest.raises(FAILED, match=r"(?s)still running.*hello"):
        run_as_process(scenario, py(code), timeout=1)


@POSIX_ONLY
def test_reset_sigint_gives_the_child_sigint_at_its_default() -> None:
    code = "import signal; print(signal.getsignal(signal.SIGINT) is signal.default_int_handler)"
    previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        reset = start(py(code), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        kept = start(
            py(code), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, reset_sigint=False
        )
    finally:
        signal.signal(signal.SIGINT, previous)
    assert reset.communicate(timeout=TIMEOUT)[0].strip() == b"True"
    assert kept.communicate(timeout=TIMEOUT)[0].strip() == b"False"


# A child standing in for tlaup: it starts the fake java as tlaup would and reacts to signals as told.
# A signal that comes before the fake's process is known is handled once it is.
CHILD = """
import os, signal, subprocess, sys, time
java, mode = sys.argv[1], sys.argv[2]
extra = sys.argv[3:]
fake = None
count = 0
def log(text):
    sys.stderr.write(text + "\\n"); sys.stderr.flush()
pending = []
def handler(number, frame):
    global count
    if fake is None:
        pending.append(number)
        return
    count += 1
    log(f"signal {count}")
    if mode == "forward-then-kill":
        if count == 1:
            fake.send_signal(signal.SIGTERM)
            return
        fake.kill(); fake.wait(); sys.exit(143)
    if mode == "hold":  # the checkpoint deferral: show the waiting line, wait for the commit, then stop
        log("release before: " + str(os.path.exists(extra[0])))
        log("tmp files: " + str(bool(list(__import__("pathlib").Path(extra[1]).rglob("*.tmp")))))
        log("waiting for TLC to finish writing its checkpoint; press Ctrl-C again to stop now")
        for _ in range(5):  # lines 1 to 3 are in the pipe; 4 and 5 come only after the release
            fake.stdout.readline()
        fake.terminate(); fake.wait(); sys.exit(130)
    if mode == "pass-on":  # a raw run: the fake gets the signal itself
        fake.send_signal(number)
        sys.exit(fake.wait() and 130)
    if mode == "again":
        if count == 1:
            log("x")
            return
        fake.kill(); fake.wait(); sys.exit(130)
    if fake is not None:
        fake.terminate(); fake.wait()
    sys.exit(143)
signal.signal(signal.SIGTERM, handler)
signal.signal(signal.SIGINT, handler)
subprocess.run([java, "-version"], capture_output=True)
args = [java, "tlc2.TLC"] + (["-metadir", extra[1]] if mode in ("hold", "pass-on", "again") else [])
if mode == "group":
    signal.signal(signal.SIGTERM, signal.SIG_DFL)
fake = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                        process_group=0 if mode in ("hold", "pass-on", "again") else None)
for number in pending:
    handler(number, None)
while True:
    signal.pause()
"""


def child(fakes: Fakes, mode: str, *extra: str | Path) -> list[str]:
    return py(CHILD, fakes.bin / "java", mode, *extra)


def java_lines(fakes: Fakes, event: str) -> list[dict[str, Any]]:
    return [line for line in fakes.log("java") if line["event"] == event]


@POSIX_ONLY
def test_once_java_is_running_waits_for_the_tool_start(scenario: Scenario, fakes: Fakes, reap: Any) -> None:
    given(scenario, "java takes 1 seconds to report its version")  # a signal during the check would show
    given(scenario, "java prints 1 lines")
    given(scenario, "java hangs after line 1")
    result = start_and_signal(scenario, child(fakes, "terminate"), "SIGTERM", "running")
    assert result.exit_code == 143
    assert [line["main"] for line in java_lines(fakes, "start")] == ["-version", "tlc2.TLC"]
    assert [line["name"] for line in java_lines(fakes, "signal")] == ["SIGTERM"]  # the child stopped it
    assert result.pgid == os.getpgrp()  # tlaup alone, in the test's group


@POSIX_ONLY
def test_twice_waits_for_the_fakes_own_signal_line(scenario: Scenario, fakes: Fakes, reap: Any) -> None:
    given(scenario, "java prints 1 lines")
    given(scenario, "java hangs after line 1")
    given(scenario, "java ignores SIGTERM")
    result = start_and_signal(scenario, child(fakes, "forward-then-kill"), "SIGTERM", "twice")
    assert result.exit_code == 143
    assert result.stderr == "signal 1\nsignal 2\n"
    assert [line["name"] for line in java_lines(fakes, "signal")] == ["SIGTERM"]


@POSIX_ONLY
def test_to_the_foreground_group_reaches_a_grandchild(scenario: Scenario, fakes: Fakes, reap: Any) -> None:
    given(scenario, "java prints 1 lines")
    given(scenario, "java hangs after line 1")
    result = start_and_signal(scenario, child(fakes, "group"), "SIGTERM", "running", group=True)
    assert result.exit_code == 143
    assert result.pgid == result.pid
    assert [line["name"] for line in java_lines(fakes, "signal")] == ["SIGTERM"]
    assert java_lines(fakes, "exit")[-1]["code"] == 143
    start_line = java_lines(fakes, "start")[-1]
    assert start_line["pgid"] == result.pgid


def declare_checkpoint(scenario: Scenario) -> Path:
    given(scenario, 'java replays "tlc/v1.7.4/violation" with exit code 12')
    given(scenario, "java begins a checkpoint after line 3 and commits it before line 5")
    given(scenario, "java hangs after line 5")
    return Path(scenario.java_runs[-1]["checkpoint"]["release_file"])


@POSIX_ONLY
def test_once_java_has_begun_its_checkpoint_releases_after_the_waiting_line(
    scenario: Scenario, fakes: Fakes, tmp_path: Path, reap: Any
) -> None:
    release = declare_checkpoint(scenario)
    result = start_and_signal(scenario, child(fakes, "hold", release, tmp_path / "meta"), "SIGINT", "checkpoint")
    assert result.exit_code == 130
    assert result.stderr is not None
    assert "tmp files: True" in result.stderr  # sent after the checkpoint line
    assert "release before: False" in result.stderr  # released only after the waiting line
    assert release.exists()
    assert sorted(p.name for p in tmp_path.joinpath("meta").rglob("*.chkpt")) == ["queue.chkpt", "vars.chkpt"]


@POSIX_ONLY
def test_no_release_when_the_fake_gets_the_signal_itself(
    scenario: Scenario, fakes: Fakes, tmp_path: Path, reap: Any
) -> None:
    release = declare_checkpoint(scenario)
    result = start_and_signal(scenario, child(fakes, "pass-on", release, tmp_path / "meta"), "SIGINT", "checkpoint")
    assert result.exit_code == 130
    assert java_lines(fakes, "exit")[-1]["code"] == 130
    assert not release.exists()


@POSIX_ONLY
def test_and_again_sends_the_second_signal_after_the_text(
    scenario: Scenario, fakes: Fakes, tmp_path: Path, reap: Any
) -> None:
    release = declare_checkpoint(scenario)
    argv = child(fakes, "again", release, tmp_path / "meta")
    result = start_and_signal(scenario, argv, "SIGINT", "checkpoint", again_once="x")
    assert result.exit_code == 130
    assert result.stderr == "signal 1\nx\nsignal 2\n"
    assert not release.exists()


def test_a_signal_the_steps_do_not_know_fails(scenario: Scenario) -> None:
    with pytest.raises(FAILED, match="SIGUSR1"):
        start_and_signal(scenario, py("pass"), "SIGUSR1", "running")


@POSIX_ONLY
def test_a_process_that_ends_before_java_runs_fails_the_wait(scenario: Scenario) -> None:
    with pytest.raises(FAILED, match="the process ended before"):
        start_and_signal(scenario, py("print('bye')"), "SIGTERM", "running")


# The terminal runner (package 18b): Linux and macOS


PTY_ONLY = pytest.mark.skipif(os.name == "nt", reason="no pty on Windows; no Windows CI (D15)")


@PTY_ONLY
def test_the_terminal_has_the_steps_size_and_terminal_type(scenario: Scenario) -> None:
    code = (
        "import os; size = os.get_terminal_size(); "
        "print(size.columns, size.lines, os.environ.get('TERM'), os.environ.get('COLUMNS'), os.environ.get('LINES'))"
    )
    result = run_in_terminal(scenario, py(code), (90, 20))
    assert result.exit_code == 0
    assert result.stdout == "90 20 xterm-256color None None\n"
    assert result.stderr == result.stdout  # both streams are the pty
    assert result.terminal_size == (90, 20)


@PTY_ONLY
def test_a_redirected_stream_reads_as_its_file(scenario: Scenario, isolated: Isolated) -> None:
    code = "import sys; print('on screen'); print('in file', file=sys.stderr)"
    result = run_in_terminal(scenario, py(code), (80, 24), redirect={"stderr": isolated.work / "err.txt"})
    assert (result.stdout, result.stderr) == ("on screen\n", "in file\n")


@PTY_ONLY
def test_two_questions_get_both_typed_answers(scenario: Scenario) -> None:
    code = "a = input('first? '); b = input('second? '); print(f'got [{a}] [{b}]')"
    result = run_in_terminal(scenario, py(code), (80, 24), answers="yes , 7")
    assert result.exit_code == 0
    assert result.stdout is not None
    assert "got [yes] [7]" in result.stdout


@PTY_ONLY
def test_ctrl_c_once_the_terminal_has_shown_two_texts(scenario: Scenario) -> None:
    code = "import time\nprint('a', flush=True)\nprint('b', flush=True)\nwhile True:\n    time.sleep(0.05)\n"
    result = ctrl_c_once_shown(scenario, py(code), (80, 24), "a", "b")
    assert result.exit_code == 130


@PTY_ONLY
def test_feed_until_fails_with_the_last_screen(scenario: Scenario) -> None:
    run = run_on_terminal(py("print('abc')"), size=(80, 24))
    with pytest.raises(FAILED, match=r"(?s)ended before.*abc"):
        run.feed_until("zzz")


@PTY_ONLY
def test_ctrl_c_once_java_has_begun_its_checkpoint(scenario: Scenario, fakes: Fakes, tmp_path: Path, reap: Any) -> None:
    release = declare_checkpoint(scenario)
    # The fake in a group of its own, as tlaup starts a parsed run's JVM (D60): the Ctrl-C reaches the child alone.
    result = ctrl_c_at_checkpoint(scenario, child(fakes, "hold", release, tmp_path / "meta"), (100, 30))
    assert result.exit_code == 130
    assert result.stdout is not None
    assert "tmp files: True" in result.stdout
    assert "release before: False" in result.stdout
    assert release.exists()
    assert not java_lines(fakes, "signal") or java_lines(fakes, "signal")[0]["name"] == "SIGTERM"


def terminal_outcome(scenario: Scenario, data: bytes, size: tuple[int, int] = (40, 5)) -> None:
    scenario.outcome = Outcome(exit_code=0, stdout="", stderr="", terminal=data, terminal_size=size)


def test_the_terminal_ends_with_the_main_screen_around_the_alternate_screen(scenario: Scenario) -> None:
    # Package 40: ?1049l restores the main screen, so what was written before ?1049h is still there.
    scenario.expected_dir = UNIT_EXPECTED
    frame = b"\x1b[H\x1b[2JLayout frame\r\nPanel"
    terminal_outcome(scenario, b"before\r\n" + ENTER_ALT + frame + LEAVE_ALT + b"Result: done\r\nbye\r\n")
    then(scenario, 'the terminal ends with the expected file "harness/terminal-end.txt"')
    then(scenario, 'the terminal contains "Result: done"')
    with pytest.raises(FAILED, match="does not show"):
        then(scenario, 'the terminal contains "Layout frame"')


def test_the_terminal_does_not_contain_sees_overwritten_text(scenario: Scenario) -> None:
    terminal_outcome(scenario, b"secret\r\x1b[2Kshown\r\n")
    then(scenario, 'the terminal contains "shown"')
    then(scenario, 'the terminal does not contain "other"')
    with pytest.raises(FAILED, match="no longer on the screen"):
        then(scenario, 'the terminal does not contain "secret"')


# The screen steps of package 40

FRAME_ONE = (
    b"\x1b[H\x1b[2J"
    + "── Status ──\r\nStarting  elapsed 00:00:00\r\n── State space progress ──\r\n── Output ──".encode()
)
FRAME_TWO = b"\x1b[H" + "── Status ──\r\nFinished  elapsed 00:00:04\r\n".encode()


def test_layout_screens_are_the_screens_before_each_frame_starts() -> None:
    data = b"header\r\n" + ENTER_ALT + FRAME_ONE + FRAME_TWO + LEAVE_ALT + b"result\r\n"
    shown = layout_screens(data, (40, 6))
    assert len(shown) == 3  # the bytes before the first home, then one screen per frame
    assert "Starting  elapsed 00:00:00" in shown[1]
    assert shown[-1].startswith("── Status ──\nFinished  elapsed 00:00:04\n── State space progress ──")
    assert layout_screens(b"header\r\n" + ENTER_ALT + FRAME_ONE, (40, 6)) == []  # never left
    assert main_screen(data) == b"header\r\nresult\r\n"
    assert main_screen(b"a" + ENTER_ALT + b"b") == b"a" + ENTER_ALT + b"b"


def test_the_layout_steps(scenario: Scenario) -> None:
    terminal_outcome(scenario, b"header\r\n" + ENTER_ALT + FRAME_ONE + FRAME_TWO + LEAVE_ALT + b"result\r\n", (40, 6))
    then(scenario, "the terminal showed the layout")
    then(scenario, 'the last layout frame contains "Finished"')
    with pytest.raises(FAILED, match="does not show 'Starting'"):
        then(scenario, 'the last layout frame contains "Starting"')
    with pytest.raises(FAILED, match="alternate screen was used"):
        then(scenario, "the terminal stayed on the main screen")
    assert terminal_end(scenario) == "header\nresult\n"


def test_the_layout_steps_fail_without_the_layout(scenario: Scenario) -> None:
    terminal_outcome(scenario, b"plain\r\n")
    then(scenario, "the terminal stayed on the main screen")
    with pytest.raises(FAILED, match="never entered"):
        then(scenario, "the terminal showed the layout")
    with pytest.raises(FAILED, match="did not show the layout"):
        then(scenario, 'the last layout frame contains "x"')
    terminal_outcome(scenario, ENTER_ALT + b"\x1b[Hno titles" + LEAVE_ALT)
    with pytest.raises(FAILED, match="panel titles"):
        then(scenario, "the terminal showed the layout")
    terminal_outcome(scenario, ENTER_ALT + FRAME_ONE)
    with pytest.raises(FAILED, match="never left"):
        then(scenario, "the terminal showed the layout")


def test_elapsed_seconds_reads_the_status_line() -> None:
    assert elapsed_seconds("Checking   elapsed 01:02:03   errors 0") == 3723
    assert elapsed_seconds("Checking") is None


ELAPSED_CHILD = """
import sys, time
def frame(word, clock):
    sys.stdout.write("\\x1b[H\\x1b[2J" + word + "  elapsed " + clock + "\\r\\n")
    sys.stdout.flush()
frame("Starting", "00:00:00")
frame("Checking", "00:00:01")
frame("Checking", "00:00:02")
frame("Other", "00:00:09")
frame("Checking", "00:00:03")
while True:
    time.sleep(0.05)
"""


@PTY_ONLY
def test_ctrl_c_once_an_elapsed_time_later(scenario: Scenario) -> None:
    # The frames come at once: the step compares the values on the screen, not the time it waited.
    found: list[int | None] = []
    result = ctrl_c_once_elapsed(scenario, py(ELAPSED_CHILD), (60, 10), "Checking", 2, found=found)
    assert found == [1, 3]  # from the first Checking frame to 00:00:03; the "Other" frame's 00:00:09 is skipped
    assert result.exit_code == 130
    assert result.terminal is not None
    assert result.terminal.count(b"elapsed") == 5


@PTY_ONLY
def test_ctrl_c_once_an_elapsed_time_later_fails_when_none_is_shown(scenario: Scenario) -> None:
    child = "import time\nprint('Checking', flush=True)\nwhile True:\n    time.sleep(0.05)\n"
    with pytest.raises(FAILED, match="has no elapsed time"):
        ctrl_c_once_elapsed(scenario, py(child), (60, 10), "Checking", 2)


def test_screen_text_keeps_lines_that_scrolled_off() -> None:
    data = b"".join(f"line {i}\r\n".encode() for i in range(1, 11))
    assert screen_text(data, (20, 3)) == "".join(f"line {i}\n" for i in range(1, 11))


def test_a_terminal_step_after_a_plain_run_fails(scenario: Scenario) -> None:
    outcome(scenario)
    with pytest.raises(FAILED, match="not on a terminal"):
        then(scenario, 'the terminal contains "x"')


# A run killed on its timeout ends the fake java too, even in a group of its own (D60)

HANGING_PARENT = """
import subprocess, sys, time
fake = subprocess.Popen([sys.argv[1], "tlc2.TLC"], stdout=subprocess.PIPE, stdin=subprocess.DEVNULL,
                        process_group=0)
fake.stdout.readline()  # the fake has started and logged its start line
print("ready", flush=True)
time.sleep(60)
"""


def fake_pid(fakes: Fakes) -> int:
    return int(java_lines(fakes, "start")[-1]["pid"])


@POSIX_ONLY
def test_a_killed_process_run_ends_its_fake_java(scenario: Scenario, fakes: Fakes, reap: Any) -> None:
    given(scenario, "java prints 1 lines")
    given(scenario, "java hangs after line 1")
    with pytest.raises(FAILED, match=r"(?s)still running.*ready"):
        run_as_process(scenario, py(HANGING_PARENT, fakes.bin / "java"), timeout=3)
    assert not _process_alive(fake_pid(fakes))


@PTY_ONLY
def test_a_killed_terminal_run_ends_its_fake_java(scenario: Scenario, fakes: Fakes, reap: Any) -> None:
    given(scenario, "java prints 1 lines")
    given(scenario, "java hangs after line 1")
    run = run_on_terminal(py(HANGING_PARENT, fakes.bin / "java"), size=(80, 24)).watch(fakes, 0)
    run.feed_until("ready")
    with pytest.raises(FAILED, match="did not end"):
        run.finish(timeout=1)
    assert not _process_alive(fake_pid(fakes))


def test_escapes_removed_include_the_two_byte_forms_and_dcs() -> None:
    data = b"\x1b7a\x1b8b\x1b=c\x1b>d\x1bPq#0;1;1\x1b\\e\x1b[1mf\x1b]0;title\x07g"
    assert without_escapes(data) == "abcdefg"


def test_a_text_is_found_across_a_wrap_but_not_across_two_lines(scenario: Scenario) -> None:
    run = TerminalRun(process=None, master=-1, size=(4, 3))  # type: ignore[arg-type]
    run.stream.feed(b"abcdef\r\ngh\r\nij")
    assert _shows(run.screen, "cdef")  # "abcd" filled the line and wrapped
    assert not _shows(run.screen, "ghij")


# The module steps of package 31


def test_a_module_source_is_copied_and_the_fake_javac_is_scripted(scenario: Scenario, isolated: Isolated) -> None:
    given(scenario, 'a module source "Queue" from the fake sources')
    assert (isolated.work / "Queue" / "modules" / "Queue.tla").is_file()
    assert (isolated.work / "Queue" / "lib" / "a.jar").is_file()
    assert "log" in script(scenario.fakes, "javac")
    with pytest.raises(FAILED, match="no fake module source"):
        given(scenario, 'a module source "Nosuch" from the fake sources')


def test_a_registered_module_is_what_a_real_add_leaves_and_the_table_reads_it(
    scenario: Scenario, isolated: Isolated
) -> None:
    given(scenario, 'the module "Queue" is registered')
    given(scenario, 'the module "Alpha" is registered')
    folder = isolated.paths.modules / "Queue"
    assert (folder / "module.json").is_file()
    assert (folder / "modules" / "Queue.tla").is_file()
    assert [path.name for path in (isolated.paths.modules / ".tmp").iterdir()] == []
    _modules.check_registered(scenario, [["module"], ["Alpha"], ["Queue"]])
    with pytest.raises(FAILED, match="the registered modules are"):
        _modules.check_registered(scenario, [["module"], ["Queue"], ["Alpha"]])
    with pytest.raises(FAILED, match="one column headed"):
        _modules.check_registered(scenario, [["name"], ["Queue"]])
    # The two modules were registered a minute apart on the scenario's clock.
    records = [read_record(isolated.paths.modules / name) for name in ("Queue", "Alpha")]
    assert [record.built_at for record in records if record is not None] == [
        "2026-11-15T00:00:00Z",
        "2026-11-15T00:01:00Z",
    ]


def test_javac_fails_with_a_recording_and_refuses_an_unknown_one(scenario: Scenario, fakes: Fakes) -> None:
    given(scenario, 'javac fails with "syntax-error"')
    assert script(fakes, "javac")["fail_with"] == "syntax-error.txt"
    with pytest.raises(FAILED, match="no recorded javac error"):
        given(scenario, 'javac fails with "nosuch"')


# The steps package 39 adds outside T5's table: the signals java received, its process group, and Ctrl-\\.

SIGNAL_FORMS = {
    ("then", "java received SIGTERM"): ("java_received", {"names": "SIGTERM"}),
    ("then", "java received SIGINT, then SIGTERM"): ("java_received", {"names": "SIGINT, then SIGTERM"}),
    ("then", "java received no signal"): ("java_received_no_signal", {}),
    ("then", "java ran in its own process group"): ("java_ran_in_its_own_process_group", {}),
    ("then", "java ran in tlaup's process group"): ("java_ran_in_tlaups_process_group", {}),
    (
        "when",
        'I start "tlaup tlc Success" in a terminal 100 by 30 and press Ctrl-\\ once the terminal has shown "a" '
        'and then "b"',
    ): (
        "i_start_in_a_terminal_and_press_ctrl_backslash_once_shown",
        {"command": "tlaup tlc Success", "width": "100", "height": "30", "first": "a", "second": "b"},
    ),
}


@pytest.mark.parametrize(("kind", "text"), list(SIGNAL_FORMS))
def test_each_signal_form_finds_its_own_step(kind: str, text: str) -> None:
    name, arguments = SIGNAL_FORMS[(kind, text)]
    context = find_step(kind, text)
    assert context.step_func.__name__ == name
    assert (context.parser.parse_arguments(text) or {}) == arguments


def test_the_signal_forms_do_not_take_each_others_text() -> None:
    # The forms that share words: "java ran ..." with a main class or a launcher, the two Ctrl- forms.
    assert find_step("then", 'java ran "tlc2.TLC" 1 time').step_func.__name__ == "java_ran_times"
    assert find_step("then", "java ran from PATH").step_func.__name__ == "java_ran_from_path"
    ctrl_c = 'I start "tlaup x" in a terminal 80 by 24 and press Ctrl-C once the terminal has shown "a" and then "b"'
    assert find_step("when", ctrl_c).step_func.__name__ == "i_start_in_a_terminal_and_press_ctrl_c_once_shown"
    for kind, text in (
        ("then", "java received"),
        ("then", "java received SIGINT then SIGTERM"),
        ("then", "java received SIGINT, SIGTERM"),
        ("then", "java received no signals"),
        ("then", "java ran in a process group"),
        ("when", 'I start "tlaup x" in a terminal 80 by 24 and press Ctrl-\\ once java has begun its checkpoint'),
    ):
        assert not [c for c in contexts(kind) if c.parser.is_matching(text)], text


def java_log(scenario: Scenario, tmp_path: Path, *lines: dict[str, Any]) -> None:
    """A java log of these lines, read by the steps as the fake's own."""
    log = tmp_path / "java-log.jsonl"
    log.write_text("".join(json.dumps(line) + "\n" for line in lines), encoding="utf-8")
    scenario.fakes.script("java", {"log": str(log)})


def tool_start(pid: int, pgid: int) -> dict[str, Any]:
    return {"event": "start", "pid": pid, "pgid": pgid, "main": "tlc2.TLC", "args": [], "run": 0}


def signal_line(pid: int, name: str) -> dict[str, Any]:
    return {"event": "signal", "pid": pid, "name": name}


@POSIX_ONLY
def test_java_received_is_every_signal_logged_in_order(scenario: Scenario, tmp_path: Path) -> None:
    java_log(scenario, tmp_path, tool_start(7, 7), signal_line(7, "SIGINT"), signal_line(7, "SIGTERM"))
    then(scenario, "java received SIGINT, then SIGTERM")
    with pytest.raises(FAILED, match=r"received \['SIGINT', 'SIGTERM'\], not \['SIGTERM'\]"):
        then(scenario, "java received SIGTERM")
    with pytest.raises(FAILED, match="not \\['SIGTERM', 'SIGINT'\\]"):
        then(scenario, "java received SIGTERM, then SIGINT")
    with pytest.raises(FAILED, match="not no signal"):
        then(scenario, "java received no signal")


@POSIX_ONLY
def test_java_received_no_signal_and_an_unknown_name(scenario: Scenario, tmp_path: Path) -> None:
    java_log(scenario, tmp_path, tool_start(7, 7))
    then(scenario, "java received no signal")
    with pytest.raises(FAILED, match="received no signal, not"):
        then(scenario, "java received SIGTERM")
    with pytest.raises(FAILED, match="not SIGKILL"):
        then(scenario, "java received SIGKILL")


@POSIX_ONLY
def test_the_process_group_steps_compare_the_last_tool_start_with_tlaup(scenario: Scenario, tmp_path: Path) -> None:
    java_log(scenario, tmp_path, tool_start(7, 5), {"event": "start", "pid": 8, "pgid": 8, "main": "-version"})
    scenario.outcome = Outcome(exit_code=0, stdout="", stderr="", pid=5, pgid=5)
    then(scenario, "java ran in tlaup's process group")
    with pytest.raises(FAILED, match="in tlaup's process group 5, not in one of its own"):
        then(scenario, "java ran in its own process group")
    java_log(scenario, tmp_path, tool_start(7, 7))
    then(scenario, "java ran in its own process group")
    with pytest.raises(FAILED, match="process group 7, not in tlaup's 5"):
        then(scenario, "java ran in tlaup's process group")


@POSIX_ONLY
def test_the_process_group_steps_need_a_real_process(scenario: Scenario, tmp_path: Path) -> None:
    java_log(scenario, tmp_path, tool_start(7, 7))
    outcome(scenario)
    with pytest.raises(FAILED, match="real process only"):
        then(scenario, "java ran in its own process group")


@PTY_ONLY
def test_ctrl_backslash_once_the_terminal_has_shown_two_texts(scenario: Scenario) -> None:
    code = (
        "import signal, sys, time\n"
        "signal.signal(signal.SIGQUIT, lambda *_: (print('quit', flush=True), sys.exit(3)))\n"
        "print('a', flush=True)\nprint('b', flush=True)\nwhile True:\n    time.sleep(0.05)\n"
    )
    result = quit_once_shown(scenario, py(code), (80, 24), "a", "b")
    assert result.exit_code == 3
    assert result.stdout is not None
    assert "quit" in result.stdout
