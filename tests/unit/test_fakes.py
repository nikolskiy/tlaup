"""The fakes of design 01 T4, each started as a real child from an argument list."""

from __future__ import annotations

import os
import select
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from tests.fakes.control import TOOLS, Fakes, Tool

if TYPE_CHECKING:
    from collections.abc import Callable

TIMEOUT = 30
POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="signals and pipes as POSIX has them; no Windows CI (D15)")
ENCODING_OPTIONS = ["-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8", "-Dstderr.encoding=UTF-8"]


def java_run(**fields: Any) -> dict[str, Any]:
    run: dict[str, Any] = {"main": "tlc2.TLC", "stdout": None, "stderr": None, "exit": 0}
    run.update(fields)
    return run


def run_tool(fakes: Fakes, tool: str, *args: str, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run([str(fakes.bin / tool), *args], capture_output=True, timeout=TIMEOUT, check=False, **kwargs)


def start_tool(fakes: Fakes, tool: str, *args: str, **kwargs: Any) -> subprocess.Popen[bytes]:
    return subprocess.Popen([str(fakes.bin / tool), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)


def finish(proc: subprocess.Popen[bytes]) -> int:
    """Wait for the child and close its pipes; kill it if it outlives the timeout."""
    try:
        return proc.wait(timeout=TIMEOUT)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
        for stream in (proc.stdout, proc.stderr, proc.stdin):
            if stream is not None:
                stream.close()


def wait_for(condition: Callable[[], Any], what: str) -> Any:
    """Wait for a condition, never for an amount of time (T12 rule 5)."""
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        result = condition()
        if result:
            return result
        time.sleep(0.01)
    pytest.fail(f"timed out waiting for {what}")


def logged(fakes: Fakes, tool: Tool, event: str, **match: Any) -> list[dict[str, Any]]:
    return [
        line for line in fakes.log(tool) if line["event"] == event and all(line.get(k) == v for k, v in match.items())
    ]


def wait_logged(fakes: Fakes, tool: Tool, event: str, **match: Any) -> dict[str, Any]:
    lines: list[dict[str, Any]] = wait_for(lambda: logged(fakes, tool, event, **match), f"a {event} line from {tool}")
    return lines[-1]


def read_lines(proc: subprocess.Popen[bytes], count: int) -> list[bytes]:
    """Read ``count`` lines from the child's stdout, failing if they cannot be read in time."""
    assert proc.stdout is not None
    fd = proc.stdout.fileno()
    data = b""
    deadline = time.monotonic() + TIMEOUT
    while data.count(b"\n") < count:
        ready, _, _ = select.select([fd], [], [], max(0.0, deadline - time.monotonic()))
        if not ready:
            pytest.fail(f"line {count} could not be read; got {data!r}")
        chunk = os.read(fd, 65536)
        if not chunk:
            pytest.fail(f"stdout closed before line {count}; got {data!r}")
        data += chunk
    return data.splitlines(keepends=True)


# The launchers and the Fakes object


def test_path_holds_only_the_four_fakes(fakes: Fakes) -> None:
    assert os.environ["PATH"] == str(fakes.bin)
    assert fakes.bin.parent.name != "" and fakes.bin.name == "bin"
    for tool in TOOLS:
        assert shutil.which(tool) == str(fakes.bin / tool)
    assert sorted(path.name for path in fakes.bin.iterdir() if not path.name.endswith(".cmd")) == sorted(TOOLS)


def test_launcher_names_the_running_interpreter(fakes: Fakes) -> None:
    first = (fakes.bin / "java").read_text(encoding="utf-8").splitlines()[0]
    assert first == f"#!{sys.executable}"


@pytest.mark.parametrize("tool", TOOLS)
def test_no_script_fails_loudly(fakes: Fakes, tool: Tool) -> None:
    result = run_tool(fakes, tool, "anything")
    assert result.returncode == 127
    assert result.stderr == f"fake {tool}: no script\n".encode()
    assert result.stdout == b""


def test_remove(fakes: Fakes) -> None:
    fakes.remove("java")
    assert shutil.which("java") is None
    assert shutil.which("javac") == str(fakes.bin / "javac")


@POSIX_ONLY
def test_not_executable(fakes: Fakes) -> None:
    fakes.not_executable("java")
    assert (fakes.bin / "java").exists()
    assert shutil.which("java") is None


def test_jdk_folder_java_logs_its_own_path(fakes: Fakes, tmp_path: Path) -> None:
    fakes.script("java", {"version": "25.0.5"})
    home = fakes.jdk(tmp_path / "jdk", {"version": "17.0.9"})
    assert home == tmp_path / "jdk"
    java = home / "bin" / "java"
    result = subprocess.run([str(java), "-version"], capture_output=True, timeout=TIMEOUT, check=False)
    assert result.returncode == 0
    assert b'"17.0.9"' in result.stderr
    run_tool(fakes, "java", "-version")
    paths = [line["path"] for line in logged(fakes, "java", "start")]
    assert paths == [str(java), str(fakes.bin / "java")]
    javac = subprocess.run([str(home / "bin" / "javac"), "-version"], capture_output=True, timeout=TIMEOUT, check=False)
    assert javac.stdout == b"javac 17.0.9\n"
    assert [line["path"] for line in logged(fakes, "javac", "start")] == [str(home / "bin" / "javac")]


# java: the version request


def test_java_version_banner(fakes: Fakes) -> None:
    fakes.script("java", {"version": "11.0.33"})
    result = run_tool(fakes, "java", "-version")
    assert result.returncode == 0
    assert result.stdout == b""
    assert result.stderr.decode().splitlines() == [
        'openjdk version "11.0.33" 2026-10-20',
        "OpenJDK Runtime Environment Temurin-11.0.33+10 (build 11.0.33+10)",
        "OpenJDK 64-Bit Server VM Temurin-11.0.33+10 (build 11.0.33+10, mixed mode)",
    ]
    start = logged(fakes, "java", "start")[0]
    assert start["main"] == "-version"
    assert start["run"] is None
    assert logged(fakes, "java", "exit") == [{"event": "exit", "pid": start["pid"], "code": 0}]


@POSIX_ONLY
def test_java_version_delay(fakes: Fakes) -> None:
    # No clock (T12 rule 5): with a long delay, nothing is on stderr once the fake has started.
    fakes.script("java", {"version_delay_ms": 60000})
    proc = start_tool(fakes, "java", "-version")
    try:
        wait_logged(fakes, "java", "start", main="-version")
        assert proc.stderr is not None
        ready, _, _ = select.select([proc.stderr.fileno()], [], [], 0)
        assert ready == []
        proc.send_signal(signal.SIGTERM)
    finally:
        code = finish(proc)
    assert code == 143


def test_java_version_object(fakes: Fakes) -> None:
    fakes.script(
        "java",
        {"version": {"stdout": "out text\n", "stderr": "Unable to locate a Java Runtime.\n", "exit": 1}},
    )
    result = run_tool(fakes, "java", "-version")
    assert result.returncode == 1
    assert result.stdout == b"out text\n"
    assert result.stderr == b"Unable to locate a Java Runtime.\n"


def test_java_version_uses_no_run(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run(stdout={"text": "ran\n"})]})
    run_tool(fakes, "java", "-version")
    result = run_tool(fakes, "java", "tlc2.TLC")
    assert result.stdout == b"ran\n"


# java: arguments and runs


def test_java_main_class_behind_options(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run(stdout={"text": "ok\n"})]})
    args = ["-javaagent:x=pid=1", *ENCODING_OPTIONS, "-cp", "a", "tlc2.TLC", "b"]
    result = run_tool(fakes, "java", *args)
    assert result.returncode == 0
    assert result.stdout == b"ok\n"
    start = logged(fakes, "java", "start")[0]
    assert start["main"] == "tlc2.TLC"
    assert start["args"] == args
    assert start["run"] == 0


def test_java_classpath_value_is_not_the_main_class(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run(main="tla2sany.SANY"), java_run(main="tla2sany.SANY")]})
    for option in ("-classpath", "--class-path"):
        result = run_tool(fakes, "java", option, "tlc2.TLC", "tla2sany.SANY")
        assert result.returncode == 0
        assert logged(fakes, "java", "start")[-1]["main"] == "tla2sany.SANY"


def test_java_replay_from_absolute_path_is_byte_for_byte(fakes: Fakes, tmp_path: Path) -> None:
    data = b"first line\n\xff\xfe not UTF-8\r\nlast line without an ending"
    capture = tmp_path / "capture.out"
    capture.write_bytes(data)
    fakes.script("java", {"runs": [java_run(stdout=str(capture), stderr=str(capture))]})
    result = run_tool(fakes, "java", "tlc2.TLC")
    assert result.stdout == data
    assert result.stderr == data


def test_java_literal_text_on_each_stream(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run(stdout={"text": "to stdout\n"}, stderr={"text": "to stderr\n"})]})
    result = run_tool(fakes, "java", "tlc2.TLC")
    assert result.stdout == b"to stdout\n"
    assert result.stderr == b"to stderr\n"


def test_java_generate_lines(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run(generate_lines=3)]})
    result = run_tool(fakes, "java", "tlc2.TLC")
    assert result.stdout == b"line 1\nline 2\nline 3\n"


def test_java_exit_code(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run(exit=12)]})
    result = run_tool(fakes, "java", "tlc2.TLC")
    assert result.returncode == 12
    assert logged(fakes, "java", "exit")[0]["code"] == 12


def test_java_each_run_answers_one_start(fakes: Fakes) -> None:
    runs = [
        java_run(stdout={"text": "first\n"}, exit=0),
        java_run(main="tla2sany.SANY", stdout={"text": "sany\n"}),
        java_run(stdout={"text": "second\n"}, exit=12),
    ]
    fakes.script("java", {"runs": runs})
    first = run_tool(fakes, "java", "tlc2.TLC")
    second = run_tool(fakes, "java", "tlc2.TLC")
    third = run_tool(fakes, "java", "tlc2.TLC")
    assert (first.stdout, first.returncode) == (b"first\n", 0)
    assert (second.stdout, second.returncode) == (b"second\n", 12)
    assert third.returncode == 127
    assert third.stderr == b"fake java: no script for tlc2.TLC\n"
    assert [line["run"] for line in logged(fakes, "java", "start")] == [0, 2, None]


def test_java_replace(fakes: Fakes) -> None:
    fakes.script(
        "java",
        {"runs": [java_run(stdout={"text": "<tmp>/q1/specs/A.tla\nkeep\n"}, replace={"<tmp>/q1/specs": "/w"})]},
    )
    result = run_tool(fakes, "java", "tlc2.TLC")
    assert result.stdout == b"/w/A.tla\nkeep\n"


def test_java_echo_stdin(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run(main="tlc2.REPL", stdout={"text": "banner\n"}, echo_stdin=True, exit=0)]})
    result = run_tool(fakes, "java", "tlc2.REPL", input=b"1 + 1\nTRUE\n")
    assert result.returncode == 0
    assert result.stdout == b"banner\n1 + 1\nTRUE\n"


def test_java_write_into_metadir(fakes: Fakes, tmp_path: Path) -> None:
    metadir = tmp_path / "states"
    fakes.script("java", {"runs": [java_run(write_into_metadir=["queue.chkpt", "vars.chkpt"])]})
    result = run_tool(fakes, "java", "tlc2.TLC", "-metadir", str(metadir), "Spec.tla")
    assert result.returncode == 0
    [folder] = list(metadir.iterdir())
    assert len(folder.name.split("-")) == 6
    assert sorted(path.name for path in folder.iterdir()) == ["queue.chkpt", "vars.chkpt"]


def test_java_metadir_fields_need_metadir(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run(write_into_metadir=["queue.chkpt"])]})
    result = run_tool(fakes, "java", "tlc2.TLC", "Spec.tla")
    assert result.returncode == 127
    assert b"-metadir" in result.stderr


def test_java_without_a_main_class_or_version_exits_127(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run()]})
    result = run_tool(fakes, "java", "-cp", "a", "-Dx=y")
    assert result.returncode == 127
    assert result.stderr == b"fake java: no main class among the arguments\n"


@POSIX_ONLY
def test_java_runs_on_when_its_stdout_is_closed(fakes: Fakes, tmp_path: Path) -> None:
    # The checkpoint line marks that the fake has written its lines into the closed pipe.
    checkpoint = {"begin_after_line": 2, "commit_before_line": 3, "release_file": None}
    run = java_run(generate_lines=2, hang_after_line=2, checkpoint=checkpoint, on_sigterm=143)
    fakes.script("java", {"runs": [run]})
    errors = tmp_path / "stderr.txt"
    with errors.open("wb") as stderr:
        proc = subprocess.Popen(
            [str(fakes.bin / "java"), "tlc2.TLC", "-metadir", str(tmp_path / "m")],
            stdout=subprocess.PIPE,
            stderr=stderr,
        )
    assert proc.stdout is not None
    proc.stdout.close()
    try:
        wait_logged(fakes, "java", "checkpoint", pid=proc.pid)
        assert proc.poll() is None
        proc.send_signal(signal.SIGTERM)
    finally:
        code = finish(proc)
    assert code == 143
    assert errors.read_bytes() == b""
    assert [line["name"] for line in logged(fakes, "java", "signal")] == ["SIGTERM"]


def test_java_start_line_fields(fakes: Fakes, tmp_path: Path) -> None:
    fakes.script("java", {"runs": [java_run(), java_run()]})
    work = tmp_path / "spec-folder"
    work.mkdir()
    piped = subprocess.run(
        [str(fakes.bin / "java"), "tlc2.TLC", "x"], cwd=work, stdout=subprocess.PIPE, timeout=TIMEOUT, check=False
    )
    with (tmp_path / "out.txt").open("wb") as out:
        to_file = subprocess.run([str(fakes.bin / "java"), "tlc2.TLC"], stdout=out, timeout=TIMEOUT, check=False)
    assert piped.returncode == to_file.returncode == 0
    first, second = logged(fakes, "java", "start")
    assert first["path"] == str(fakes.bin / "java")
    assert first["args"] == ["tlc2.TLC", "x"]
    assert first["cwd"] == str(work)
    assert first["main"] == "tlc2.TLC"
    assert first["stdout_pipe"] is True
    assert second["stdout_pipe"] is False
    assert isinstance(first["pid"], int)
    assert first["ignored_signals"] == []
    if hasattr(os, "getpgrp"):
        assert isinstance(first["pgid"], int)


@POSIX_ONLY
def test_java_process_group(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run()]})
    proc = start_tool(fakes, "java", "tlc2.TLC", start_new_session=True)
    assert finish(proc) == 0
    start = logged(fakes, "java", "start")[0]
    assert start["pgid"] == start["pid"] == proc.pid


# java: hangs and signals


def hanging(fakes: Fakes, **fields: Any) -> subprocess.Popen[bytes]:
    fakes.script("java", {"runs": [java_run(generate_lines=2, hang_after_line=2, **fields)]})
    proc = start_tool(fakes, "java", "tlc2.TLC")
    assert read_lines(proc, 2) == [b"line 1\n", b"line 2\n"]
    wait_logged(fakes, "java", "start")
    return proc


@POSIX_ONLY
def test_java_sigterm_gives_on_sigterm(fakes: Fakes) -> None:
    proc = hanging(fakes, on_sigterm=143)
    proc.send_signal(signal.SIGTERM)
    assert finish(proc) == 143
    assert [line["name"] for line in logged(fakes, "java", "signal")] == ["SIGTERM"]
    assert logged(fakes, "java", "exit")[0]["code"] == 143


@POSIX_ONLY
def test_java_sigint_gives_on_sigint(fakes: Fakes) -> None:
    proc = hanging(fakes, on_sigint=130)
    proc.send_signal(signal.SIGINT)
    assert finish(proc) == 130


@POSIX_ONLY
def test_java_ignore_keeps_it_running(fakes: Fakes) -> None:
    proc = hanging(fakes, on_sigterm="ignore", on_sigint=130)
    proc.send_signal(signal.SIGTERM)
    wait_logged(fakes, "java", "signal", name="SIGTERM")
    assert proc.poll() is None
    proc.send_signal(signal.SIGINT)
    assert finish(proc) == 130


@POSIX_ONLY
def test_java_logs_two_signals_sent_back_to_back_in_order(fakes: Fakes) -> None:
    # A terminal's SIGINT and tlaup's SIGTERM together: neither line is lost to the other's handler (package 39b).
    proc = hanging(fakes, on_sigint="ignore", on_sigterm=143)
    os.kill(proc.pid, signal.SIGINT)
    os.kill(proc.pid, signal.SIGTERM)
    assert finish(proc) == 143
    assert [line["name"] for line in logged(fakes, "java", "signal")] == ["SIGINT", "SIGTERM"]
    assert logged(fakes, "java", "exit")[0]["code"] == 143


@POSIX_ONLY
def test_java_sigquit_is_logged_and_survived(fakes: Fakes) -> None:
    proc = hanging(fakes, on_sigterm=143)
    proc.send_signal(signal.SIGQUIT)
    wait_logged(fakes, "java", "signal", name="SIGQUIT")
    assert proc.poll() is None
    proc.send_signal(signal.SIGTERM)
    assert finish(proc) == 143


@POSIX_ONLY
def test_java_sighup_gives_129(fakes: Fakes) -> None:
    proc = hanging(fakes)
    proc.send_signal(signal.SIGHUP)
    assert finish(proc) == 129
    assert [line["name"] for line in logged(fakes, "java", "signal")] == ["SIGHUP"]


@POSIX_ONLY
def test_java_signal_ignored_at_start_stays_ignored(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run(generate_lines=1, hang_after_line=1, on_sigterm=143)]})
    # Ignore SIGHUP, then exec the launcher, as nohup does: the disposition survives exec.
    ignore_then_exec = (
        "import os, signal, sys; signal.signal(signal.SIGHUP, signal.SIG_IGN); os.execv(sys.argv[1], sys.argv[1:])"
    )
    proc = subprocess.Popen(
        [sys.executable, "-c", ignore_then_exec, str(fakes.bin / "java"), "tlc2.TLC"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        read_lines(proc, 1)
        start = wait_logged(fakes, "java", "start")
        assert start["ignored_signals"] == ["SIGHUP"]
        proc.send_signal(signal.SIGHUP)
        proc.send_signal(signal.SIGTERM)
    finally:
        code = finish(proc)
    assert code == 143
    assert [line["name"] for line in logged(fakes, "java", "signal")] == ["SIGTERM"]


# java: the checkpoint


def checkpoint_script(fakes: Fakes, release: Path | None) -> None:
    checkpoint = {"begin_after_line": 2, "commit_before_line": 3, "release_file": str(release) if release else None}
    run = java_run(generate_lines=4, hang_after_line=3, checkpoint=checkpoint, on_sigterm=143)
    fakes.script("java", {"runs": [run, run]})


def names(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir())


@POSIX_ONLY
def test_java_checkpoint_waits_for_its_release(fakes: Fakes, tmp_path: Path) -> None:
    release = tmp_path / "release"
    checkpoint_script(fakes, release)

    # First start: the checkpoint line comes once line 2 is readable; a SIGTERM while the
    # fake waits for its release leaves the .tmp files and no .chkpt.
    first = start_tool(fakes, "java", "tlc2.TLC", "-metadir", str(tmp_path / "m1"))
    try:
        line = wait_logged(fakes, "java", "checkpoint", pid=first.pid)
        folder = Path(line["folder"])
        assert folder.parent == tmp_path / "m1"
        assert names(folder) == ["queue.tmp", "vars.tmp"]
        assert read_lines(first, 2) == [b"line 1\n", b"line 2\n"]
        first.send_signal(signal.SIGTERM)
    finally:
        code = finish(first)
    assert code == 143
    assert names(folder) == ["queue.tmp", "vars.tmp"]

    # Second start: once the release file exists, the .chkpt files are there by the time
    # line 3 can be read; then the fake hangs until SIGTERM.
    second = start_tool(fakes, "java", "tlc2.TLC", "-metadir", str(tmp_path / "m2"))
    try:
        folder = Path(wait_logged(fakes, "java", "checkpoint", pid=second.pid)["folder"])
        assert names(folder) == ["queue.tmp", "vars.tmp"]
        release.touch()
        assert read_lines(second, 3)[-1] == b"line 3\n"
        assert names(folder) == ["queue.chkpt", "vars.chkpt"]
        assert second.poll() is None
        second.send_signal(signal.SIGTERM)
    finally:
        code = finish(second)
    assert code == 143


def test_java_checkpoint_without_release_goes_straight_on(fakes: Fakes, tmp_path: Path) -> None:
    checkpoint = {"begin_after_line": 2, "commit_before_line": 3, "release_file": None}
    fakes.script("java", {"runs": [java_run(generate_lines=4, checkpoint=checkpoint)]})
    result = run_tool(fakes, "java", "tlc2.TLC", "-metadir", str(tmp_path / "m"))
    assert result.returncode == 0
    assert result.stdout == b"line 1\nline 2\nline 3\nline 4\n"
    folder = Path(logged(fakes, "java", "checkpoint")[0]["folder"])
    assert names(folder) == ["queue.chkpt", "vars.chkpt"]


def test_java_quiet_on_stderr_unless_scripted(fakes: Fakes) -> None:
    fakes.script("java", {"runs": [java_run(generate_lines=2)]})
    assert run_tool(fakes, "java", "tlc2.TLC").stderr == b""


# javac


def test_javac_version(fakes: Fakes) -> None:
    fakes.script("javac", {"version": "21.0.4"})
    result = run_tool(fakes, "javac", "-version")
    assert (result.returncode, result.stdout, result.stderr) == (0, b"javac 21.0.4\n", b"")


def test_javac_version_default(fakes: Fakes) -> None:
    fakes.script("javac", {})
    assert run_tool(fakes, "javac", "-version").stdout == b"javac 25.0.5\n"


def test_javac_copies_the_prepared_class(fakes: Fakes, tmp_path: Path) -> None:
    fakes.script("javac", {})
    out = tmp_path / "out"
    source = tmp_path / "src" / "Plain.java"
    result = run_tool(fakes, "javac", "--release", "11", "-cp", "lib.jar", "-d", str(out), str(source))
    assert result.returncode == 0
    prepared = Path(__file__).parents[1] / "fakes" / "classes" / "plain" / "Plain.class"
    assert (out / "plain" / "Plain.class").read_bytes() == prepared.read_bytes()
    start = logged(fakes, "javac", "start")[0]
    assert start["args"][-1] == str(source)


def test_javac_missing_class(fakes: Fakes, tmp_path: Path) -> None:
    fakes.script("javac", {})
    result = run_tool(fakes, "javac", "-d", str(tmp_path / "out"), "Other.java")
    assert result.returncode == 2
    assert result.stderr == b"fake javac: no prepared class for Other.java\n"
    assert not (tmp_path / "out").exists()


def test_javac_without_d_exits_127(fakes: Fakes) -> None:
    fakes.script("javac", {})
    result = run_tool(fakes, "javac", "Plain.java")
    assert result.returncode == 127
    assert result.stderr == b"fake javac: no -d folder among the arguments\n"


def test_javac_fail_with(fakes: Fakes, tmp_path: Path) -> None:
    error = tmp_path / "error.txt"
    error.write_bytes(b"Plain.java:3: error: ';' expected\n1 error\n")
    fakes.script("javac", {"fail_with": str(error)})
    result = run_tool(fakes, "javac", "-d", str(tmp_path / "out"), "Plain.java")
    assert result.returncode == 1
    assert result.stderr == error.read_bytes()
    assert logged(fakes, "javac", "exit")[0]["code"] == 1


# git and the editor


def test_git_default_answer(fakes: Fakes) -> None:
    fakes.script("git", {})
    result = run_tool(fakes, "git", "rev-parse", "--short", "HEAD")
    assert (result.returncode, result.stdout) == (0, b"abc1234\n")
    assert logged(fakes, "git", "start")[0]["args"] == ["rev-parse", "--short", "HEAD"]


def test_git_scripted_answer(fakes: Fakes) -> None:
    fakes.script("git", {"stdout": "", "exit": 128})
    assert run_tool(fakes, "git", "status").returncode == 128


def test_editor_default_leaves_the_file(fakes: Fakes, tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("old\n", encoding="utf-8")
    fakes.script("editor", {})
    result = run_tool(fakes, "editor", "--wait", str(target))
    assert result.returncode == 0
    assert target.read_text(encoding="utf-8") == "old\n"
    assert logged(fakes, "editor", "start")[0]["args"] == ["--wait", str(target)]


def test_editor_writes_and_exits(fakes: Fakes, tmp_path: Path) -> None:
    target = tmp_path / "config.toml"
    target.write_text("old\n", encoding="utf-8")
    fakes.script("editor", {"write": "new = 1\n", "exit": 3})
    result = run_tool(fakes, "editor", str(target))
    assert result.returncode == 3
    assert target.read_text(encoding="utf-8") == "new = 1\n"
    assert logged(fakes, "editor", "exit")[0]["code"] == 3
