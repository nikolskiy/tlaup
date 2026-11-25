"""The agent with a real JVM (design 20 G3, "The lifeline"). Each test starts the jar that ships."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

from tests.lifeline.procs import kill_quietly, running, wait_until

if TYPE_CHECKING:
    from pathlib import Path

# A stand-in for tlaup: starts the JVM with the agent naming this process, tells the test the JVM's id, then waits.
PARENT = textwrap.dedent(
    """
    import subprocess, sys
    java, jar, classes, ready = sys.argv[1:5]
    extra = sys.argv[5:]
    import os
    child = subprocess.Popen(
        [java, f"-javaagent:{jar}=pid={os.getpid()}", *extra, "-cp", classes, "Sleeper", ready],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print(child.pid, flush=True)
    sys.stdin.read()
    """
)
GONE_WITHIN = 3.0
UP_WITHIN = 60.0


def start_with_agent(java: str, jar: Path, classes: Path, argument: str, *more: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [java, f"-javaagent:{jar}={argument}", "-cp", str(classes), "Sleeper", *more],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


@pytest.mark.parametrize("jvm_options", [[], ["-Xrs"]], ids=["plain", "xrs"])
def test_jvm_ends_when_its_parent_is_killed(
    tmp_path: Path, jar: Path, java: str, test_classes: Path, jvm_options: list[str]
) -> None:
    ready = tmp_path / "ready"
    parent = subprocess.Popen(
        [sys.executable, "-c", PARENT, java, str(jar), str(test_classes), str(ready), *jvm_options],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert parent.stdout is not None
    assert parent.stdin is not None
    jvm = int(parent.stdout.readline())
    try:
        wait_until(ready.exists, "the JVM is up", UP_WITHIN)
        assert running(jvm)
        parent.kill()  # SIGKILL, or TerminateProcess on Windows: no handler of the parent runs
        parent.wait(timeout=30)
        wait_until(lambda: not running(jvm), "the JVM is gone", GONE_WITHIN)
    finally:
        kill_quietly(jvm)
        parent.stdout.close()
        parent.stdin.close()
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=30)


def test_jvm_exits_at_once_for_a_process_that_has_gone(
    tmp_path: Path, jar: Path, java: str, test_classes: Path
) -> None:
    done = subprocess.run(
        [sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True, check=True
    )
    ready = tmp_path / "ready"
    jvm = start_with_agent(java, jar, test_classes, f"pid={done.stdout.strip()}", str(ready))
    try:
        out, err = jvm.communicate(timeout=GONE_WITHIN * 10)
    finally:
        if jvm.poll() is None:
            kill_quietly(jvm.pid)
            jvm.wait(timeout=30)
    assert jvm.returncode == 143
    assert not ready.exists(), "the tool started although the process was already gone"
    assert (out, err) == ("", "")


@pytest.mark.parametrize("argument", ["", "pid=", "pid=abc", "pid=12x", "pid=-5", "12", "pid=" + "9" * 40], ids=repr)
def test_malformed_argument_does_nothing(
    tmp_path: Path, jar: Path, java: str, test_classes: Path, argument: str
) -> None:
    """The agent ignores an argument that is not `pid=<digits>`: the tool runs as if there were no agent."""
    ready = tmp_path / "ready"
    jvm = start_with_agent(java, jar, test_classes, argument, str(ready), "quick")
    out, err = jvm.communicate(timeout=UP_WITHIN)
    assert jvm.returncode == 0
    assert ready.exists()
    assert (out, err) == ("", "")


def test_agent_with_a_live_process_prints_nothing_and_does_not_hold_the_jvm(
    tmp_path: Path, jar: Path, java: str, test_classes: Path
) -> None:
    """The watcher is a daemon: a tool that finishes ends, and the agent writes to no stream."""
    ready = tmp_path / "ready"
    jvm = start_with_agent(java, jar, test_classes, f"pid={os.getpid()}", str(ready), "quick")
    out, err = jvm.communicate(timeout=UP_WITHIN)
    assert jvm.returncode == 0
    assert (out, err) == ("", "")


def unshare_prefix() -> list[str] | None:
    """The `unshare` command that makes a process-id namespace here, or None when this system does not allow it."""
    unshare = shutil.which("unshare")
    if unshare is None:
        return None
    for extra in ([], ["--user", "--map-root-user"]):
        prefix = [unshare, *extra, "--pid", "--fork", "--mount-proc"]
        probe = subprocess.run([*prefix, "true"], capture_output=True, check=False)
        if probe.returncode == 0:
            return prefix
    return None


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="a process-id namespace exists on Linux only")
def test_a_reused_process_id_is_not_taken_for_the_original(java: str, test_classes: Path) -> None:
    """The agent rests on `isAlive` comparing start times; this confirms the JDK's behaviour (G3), not tlaup's."""
    prefix = unshare_prefix()
    if prefix is None:
        reason = "no process-id namespace here (needs `unshare` with root, or user namespaces)"
        if os.environ.get("CI"):
            pytest.fail(reason + "; the CI job must provide it")
        pytest.skip(reason)
    done = subprocess.run(
        [*prefix, java, "-cp", str(test_classes), "ReusedId"], capture_output=True, text=True, check=False, timeout=120
    )
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() != "NO-REUSE", "the stand-in could not arrange a reused process id"
    assert done.stdout.strip() == "GONE", f"the old handle still says alive after its id was reused: {done.stdout!r}"
