"""The feature harness's helpers and the steps no scenario of package 18 uses (design 01 T5, T12 rule 10).

Each step is called through its own step function, found by its text as pytest-bdd finds it, on a real
``Scenario``; the fakes are started from the test as real children (no patching, T12 rule 2).
"""

from __future__ import annotations

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

from tests.steps._scenario import GOLDEN_DIR, PASSTHROUGH, STARTUP_ONLY, TLAUP_JAVA_DIR, Outcome

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
]


@pytest.mark.parametrize("text", GIVEN_FORMS)
def test_each_given_form_finds_one_step(text: str) -> None:
    find_step("given", text)


@pytest.mark.parametrize("text", THEN_FORMS)
def test_each_then_form_finds_one_step(text: str) -> None:
    find_step("then", text)


def test_the_when_form_finds_one_step() -> None:
    assert find_step("when", 'I run "tlaup tlc Spec"').step_func.__name__ == "i_run"


def test_the_terminal_forms_do_not_match_the_in_process_step() -> None:
    for text in [
        'I run "tlaup x" in a terminal 100 by 30 and answer "y"',
        'I run "tlaup x" in a terminal 100 by 30 with stdout redirected to "out.txt"',
    ]:
        assert not [c for c in contexts("when") if c.parser.is_matching(text)], text


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


def test_steps_owned_by_later_packages_are_not_here() -> None:
    for kind, text in [
        ("given", 'the build "v1.7.4" is installed'),
        ("given", 'GitHub answers from "releases"'),
        ("given", 'javac fails with "error"'),
        ("given", 'a module source "Foo" from the fake sources'),
        ("then", 'the pinned build is "v1.7.4"'),
        ("then", "the terminal showed the layout"),
        ("then", "1 request was sent to GitHub"),
    ]:
        assert not [c for c in contexts(kind) if c.parser.is_matching(text)], text


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
    assert scenario.expand("{a: 1, b: {kept-id}} {}") == "{a: 1, b: {kept-id}} {}"


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
