"""Signals with the real JVM, and tlaup killed with SIGKILL (01 T9; 11 R2, R6; 20 G3; D51; inventory R14 with a JVM).

tlaup runs as a real process (T5) on the spec that runs until stopped; each signal goes to the tlaup process alone,
as the feature scenarios of 39 send it, once TLC has made its folder under the run folder (package 52). The JVM is
found with ``pgrep -P``; after tlaup has ended, none of it may be left. The two-SIGINT scenario holds the JVM's exit
with a small test agent (``specs/slow-exit/``), so that the second signal comes after the first has acted. The
``reaper`` fixture kills by process id whatever is still alive at the end, whatever the outcome.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
import zipfile
from typing import TYPE_CHECKING

import pytest
from typer.testing import CliRunner

import tlaup.cli
from tests.integration.live import GONE_SECONDS, SPECS, alive, copy_folder, still_alive, tlc_folder, wait_until
from tlaup.java.launcher import GRACE_SECONDS
from tlaup.java.locate import locate

if TYPE_CHECKING:
    from pathlib import Path

    from tests.integration.conftest import Isolated
    from tests.integration.live import Reaper, Running
    from tlaup.versioning.store import Build

pytestmark = [
    pytest.mark.skipif(not hasattr(signal, "SIGKILL"), reason="POSIX signals; no Windows CI (D15)"),
    pytest.mark.skipif(shutil.which("pgrep") is None, reason="pgrep is not on PATH; it finds the JVM tlaup started"),
]

INTERRUPTED = 130  # 128 + SIGINT (02 X1, 11 R2)
TERMINATED = 143  # 128 + SIGTERM
IN_USE = 5  # FileOperationError: the run's lock is held (11 R6, D51)
ATTEMPTS = 3  # the cache clean refusal races the lifeline's two seconds; the package bounds the repeats
SCENARIOS = [  # 11 R2's first two, each in parsed and in raw mode; the third is test_two_sigints_kill_the_jvm
    pytest.param("SIGTERM", TERMINATED, id="sigterm"),
    pytest.param("SIGINT", INTERRUPTED, id="sigint"),
]
MODES = {"parsed": (), "raw": ("--raw",)}


def start_forever(
    isolated: Isolated, reaper: Reaper, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *args: str
) -> Running:
    folder = isolated.work / "forever"
    if not folder.exists():
        copy_folder(SPECS / "forever", folder)
    monkeypatch.chdir(folder)
    streams = tmp_path / f"streams-{len(reaper.started)}"
    return reaper.start(["tlc", "Forever.tla", *args], streams)


@pytest.mark.parametrize("mode", list(MODES))
@pytest.mark.parametrize(("name", "code"), SCENARIOS)
def test_signal_to_tlaup_leaves_no_java(
    live_build: Build,
    isolated: Isolated,
    reaper: Reaper,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    name: str,
    code: int,
) -> None:
    """11 R2 with the real JVM: SIGTERM gives 143 and SIGINT 130, with no traceback; no JVM is left."""
    run = start_forever(isolated, reaper, tmp_path, monkeypatch, *MODES[mode])
    jvm = reaper.watch(run.jvm(isolated.paths))
    run.send(getattr(signal, name))
    assert run.wait() == code, run.output()
    assert "Traceback" not in run.stderr(), run.output()
    assert still_alive(jvm) == [], f"the JVM tlaup started is still running{run.output()}"


def slow_exit_agent(folder: Path) -> Path:
    """specs/slow-exit/SlowExit.java compiled with the real javac and packed as an agent jar (a zip with a manifest)."""
    javac = locate("javac", os.environ).tool  # as tlaup finds it: JAVA_HOME/bin first, then PATH (13 J2)
    assert javac is not None, "javac was found neither in JAVA_HOME/bin nor on PATH"
    classes = folder / "classes"
    source = SPECS / "slow-exit" / "SlowExit.java"
    command = [str(javac.path), "--release", "11", "-d", str(classes), str(source)]
    compiled = subprocess.run(command, capture_output=True, text=True, check=False)
    assert compiled.returncode == 0, compiled.stderr
    jar = folder / "slow-exit.jar"
    with zipfile.ZipFile(jar, "w") as archive:
        archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\nPremain-Class: SlowExit\n\n")
        archive.write(classes / "SlowExit.class", "SlowExit.class")
    return jar


@pytest.mark.parametrize("mode", list(MODES))
def test_two_sigints_kill_the_jvm(
    live_build: Build,
    isolated: Isolated,
    reaper: Reaper,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """11 R2: a second SIGINT kills the JVM at once; 130, no traceback, no JVM left.

    Two SIGINTs sent back to back reach Python's handler once, so the second is sent only after the first has
    visibly acted: a test agent's shutdown hook marks that the JVM got the forwarded SIGTERM and holds its exit.
    The second signal then took the kill path when tlaup ends well before the launcher's grace period, after which
    tlaup would kill the JVM by itself.
    """
    agent = slow_exit_agent(tmp_path / "agent")
    marker = tmp_path / "agent" / "shutdown-started"
    option = f"-javaagent:{agent}={marker}"
    run = start_forever(isolated, reaper, tmp_path, monkeypatch, "--java-opt", option, *MODES[mode])
    jvm = reaper.watch(run.jvm(isolated.paths))
    run.send(signal.SIGINT)
    wait_until(marker.exists, what="the JVM's shutdown after the first SIGINT (the agent's marker)", ended=run.ended)
    assert not run.ended(), run.output()
    assert all(alive(pid) for pid in jvm), "the JVM ended although the agent holds its exit"
    second_at = time.monotonic()
    run.send(signal.SIGINT)
    assert run.wait() == INTERRUPTED, run.output()
    took = time.monotonic() - second_at
    assert took < GRACE_SECONDS / 2, f"tlaup took {took:.1f} s after the second SIGINT: the grace period, not a kill"
    assert "Traceback" not in run.stderr(), run.output()
    assert still_alive(jvm) == [], f"the JVM tlaup started is still running{run.output()}"


def test_sigkill_leaves_no_java(
    live_build: Build,
    isolated: Isolated,
    reaper: Reaper,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D51: the lifeline ends the JVM of a killed tlaup within seconds; until then it holds the run's lock, so a
    second tlaup's ``cache clean <run-id>`` is refused (11 R6). Repeated with a new run when the JVM was gone
    before or after the command, up to three times (package 52)."""
    timings = []
    for attempt in range(1, ATTEMPTS + 1):
        run = start_forever(isolated, reaper, tmp_path, monkeypatch)
        jvm = reaper.watch(run.jvm(isolated.paths))
        made = tlc_folder(isolated.paths)
        assert made is not None
        run_id = made.parent.name
        killed_at = time.monotonic()  # the five seconds run from the kill (D51)
        run.send(signal.SIGKILL)
        run.wait()
        before = all(alive(pid) for pid in jvm)
        clean = CliRunner().invoke(tlaup.cli.app, ["cache", "clean", run_id])
        after = all(alive(pid) for pid in jvm)
        remaining = max(0.0, GONE_SECONDS - (time.monotonic() - killed_at))
        assert still_alive(jvm, timeout=remaining) == [], (
            f"the JVM of a tlaup killed with SIGKILL is still running{run.output()}"
        )
        if before and after:
            assert clean.exit_code == IN_USE, clean.output
            assert (isolated.paths.runs / run_id).is_dir()
            print(f"cache clean refused on attempt {attempt} of {ATTEMPTS}")  # shown by -rP, for the pull request
            return
        timings.append(f"attempt {attempt}: JVM alive before the command {before}, after it {after}")
        if (isolated.paths.runs / run_id).is_dir():  # cleaned now that the JVM is gone, so the next run is the one
            left = CliRunner().invoke(tlaup.cli.app, ["cache", "clean", run_id])
            assert left.exit_code == 0, left.output
    pytest.fail(f"the JVM was gone before the refusal could be seen, {ATTEMPTS} times: {'; '.join(timings)}")
