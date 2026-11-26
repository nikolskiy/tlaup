"""Running the real tools from the integration tests: through the Python API, and tlaup as a real process (01 T9).

The API forms are the ones T9 names (``run_tlc`` with a ``CollectingReporter``, ``run_sany``, ``run_pcal``), driven
through the same preflight the commands use; the real-process form is for a command that passes the terminal through
or a signal that must reach a process (T5's situations 1 and 3). Every function reads the environment the isolation
fixture built, as the commands would.
"""

from __future__ import annotations

import contextlib
import os
import random
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal, TypeVar

from tests.parse.facts import facts_for
from tests.steps._process import exit_code_of, start
from tests.steps._scenario import POLL_SECONDS, _process_alive
from tlaup.config.loader import load_settings
from tlaup.reporters.collecting import CollectingReporter
from tlaup.tlc.command import build_tlc_command
from tlaup.tlc.invocation import TlcRequest, resolve_tlc_invocation
from tlaup.tlc.runner import RunOutcome, run_tlc
from tlaup.tools.invocation import ToolInvocation, build_tool_command, resolve_tool_invocation
from tlaup.tools.pcal import PcalOutcome, run_pcal
from tlaup.tools.sany import SanyOutcome, run_sany

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from tlaup.java.launcher import JavaInvocation
    from tlaup.paths import AppPaths
    from tlaup.versioning.store import Build
    from tlaup_parse import Diagnostic, RunResult

REPO = Path(__file__).resolve().parents[2]
SPECS = Path(__file__).resolve().parent / "specs"  # the inputs no golden spec provides
EXAMPLES = REPO / "docs" / "examples"
T = TypeVar("T")
PROCESS_SECONDS = 120.0  # a real tlaup that has not ended by then is killed and the test fails


def utc_now() -> datetime:
    return datetime.now(UTC)


def copy_folder(source: Path, target: Path) -> Path:
    """A copy to run on, so that nothing a tool writes beside a spec lands in the repository."""
    shutil.copytree(source, target)
    return target


@dataclass
class Live:
    """One TLC run through the API: its outcome, and what the reporter and the notices received."""

    outcome: RunOutcome
    reporter: CollectingReporter
    notices: list[str]
    command: JavaInvocation  # what was started: build_tlc_command's answer


def run_live_tlc(
    paths: AppPaths,
    build: Build,
    spec: Path,
    *,
    cwd: Path,
    home: Path,
    workers: str | None = None,
    java_opts: Sequence[str] = (),
    extra_args: Sequence[str] = (),
    cfg: str | None = None,
) -> Live:
    """The preflight, the command builder and ``run_tlc`` with a ``CollectingReporter``, as ``tlaup tlc`` runs them.

    The test has entered ``cwd`` already (the JVM starts in the working folder, D34).
    """
    env = dict(os.environ)
    request = TlcRequest(
        spec=str(spec), cfg=cfg, workers=workers, java_opts=tuple(java_opts), extra_args=tuple(extra_args)
    )
    inv = resolve_tlc_invocation(
        request,
        paths=paths,
        settings=load_settings(paths, env).settings,
        env=env,
        cwd=cwd,
        home=home,
        get_build=lambda: build,
        now=utc_now,
        rng=random.SystemRandom(),
    )
    reporter = CollectingReporter()
    notices: list[str] = []
    command = build_tlc_command(inv)
    outcome = run_tlc(inv, command, reporter, paths=paths, now=utc_now, notice=notices.append)
    return Live(outcome, reporter, notices, command)


@dataclass
class Collected:
    """A sink for ``run_sany`` and ``run_pcal`` that keeps what it is given."""

    chatter_lines: list[str] = field(default_factory=list)
    other_lines: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    labels: list[tuple[str, int, int]] = field(default_factory=list)
    finished: list[object] = field(default_factory=list)

    def chatter(self, line: str) -> None:
        self.chatter_lines.append(line)

    def other(self, line: str) -> None:
        self.other_lines.append(line)

    def diagnostic(self, diagnostic: Diagnostic) -> None:
        self.diagnostics.append(diagnostic)

    def label(self, name: str, line: int, column: int) -> None:
        self.labels.append((name, line, column))


def _tool(
    tool: Literal["sany", "pcal"], paths: AppPaths, build: Build, spec: Path, *, cwd: Path, home: Path
) -> tuple[ToolInvocation, JavaInvocation]:
    env = dict(os.environ)
    inv = resolve_tool_invocation(
        tool,
        str(spec),
        java_opts=(),
        extra_args=(),
        paths=paths,
        settings=load_settings(paths, env).settings,
        env=env,
        cwd=cwd,
        home=home,
        now=utc_now,
        get_build=lambda: build,
    )
    return inv, build_tool_command(inv)


def run_live_sany(paths: AppPaths, build: Build, spec: Path, *, cwd: Path, home: Path) -> tuple[SanyOutcome, Collected]:
    inv, java_inv = _tool("sany", paths, build, spec, cwd=cwd, home=home)
    sink = Collected()
    return run_sany(inv, java_inv, sink, sink.finished.append), sink


def run_live_pcal(paths: AppPaths, build: Build, spec: Path, *, cwd: Path, home: Path) -> tuple[PcalOutcome, Collected]:
    inv, java_inv = _tool("pcal", paths, build, spec, cwd=cwd, home=home)
    sink = Collected()
    return run_pcal(inv, java_inv, sink, sink.finished.append), sink


@dataclass(frozen=True)
class Finished:
    exit_code: int
    stdout: str
    stderr: str


def run_tlaup(args: Sequence[str], *, stdin: bytes = b"", timeout: float = PROCESS_SECONDS) -> Finished:
    """``python -m tlaup ARGS`` as a real process in the working folder, with the isolation fixture's environment
    and SIGINT at its default (T5); stdin given, stdout and stderr captured. Killed by its pid after ``timeout``."""
    process = start(
        [sys.executable, "-m", "tlaup", *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    try:
        out, err = process.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        out, err = process.communicate()
        message = f"tlaup {' '.join(args)} was still running after {timeout} s; it was killed\n{out!r}\n{err!r}"
        raise AssertionError(message) from None
    return Finished(exit_code_of(process.returncode), out.decode("utf-8", "replace"), err.decode("utf-8", "replace"))


def java_children(pid: int) -> list[int]:
    """The processes ``pid`` started, by ``pgrep -P`` (Linux and macOS): how a test finds the JVM tlaup started."""
    pgrep = shutil.which("pgrep")
    if pgrep is None:
        return []
    done = subprocess.run([pgrep, "-P", str(pid)], capture_output=True, text=True, check=False)
    return [int(word) for word in done.stdout.split()]


def facts_failures(case: str, line: str, result: RunResult) -> list[str]:
    """Every fact of ``case`` for ``line`` that does not hold for ``result``, as ``<id>: <message>``."""
    failures = []
    for fact in facts_for(case, line):
        try:
            fact.check(result)
        except AssertionError as error:
            failures.append(f"{fact.id}: {error}")
    return failures


# --- tlaup as a real process that a test signals, and the JVM it started (package 52b) -------------------------

WAIT_SECONDS = 60.0  # a condition a test waits for (TLC's folder, the JVM, the end) that has not come by then fails it
GONE_SECONDS = 5.0  # D51 and 11 R6: no JVM tlaup started is alive this long after tlaup has ended


def alive(pid: int) -> bool:
    """True while ``pid`` exists and is not a zombie (POSIX; on macOS an unreaped zombie counts as alive)."""
    return _process_alive(pid)


def wait_until(
    condition: Callable[[], T | None], *, what: str, timeout: float = WAIT_SECONDS, ended: Callable[[], bool] = bool
) -> T:
    """Poll ``condition`` until it gives a value other than None or false; fail naming ``what`` after ``timeout``,
    or as soon as ``ended()`` is true and the condition still does not hold (T12 rule 5: a condition, never a time)."""
    deadline = time.monotonic() + timeout
    while True:
        stopped = ended()
        value = condition()
        if value:
            return value
        if stopped:
            message = f"the process ended before {what}"
            raise AssertionError(message)
        if time.monotonic() >= deadline:
            message = f"{what} did not happen within {timeout} seconds"
            raise AssertionError(message)
        time.sleep(POLL_SECONDS)


def still_alive(pids: Sequence[int], *, timeout: float = GONE_SECONDS) -> list[int]:
    """The processes of ``pids`` still alive after waiting up to ``timeout`` for every one to be gone."""
    deadline = time.monotonic() + timeout
    left = [pid for pid in pids if alive(pid)]
    while left and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        left = [pid for pid in left if alive(pid)]
    return left


def run_folders(paths: AppPaths) -> list[Path]:
    """The run folders under ``paths.runs`` (the lock files beside them are not folders)."""
    if not paths.runs.is_dir():
        return []
    return sorted(entry for entry in paths.runs.iterdir() if entry.is_dir())


def tlc_folder(paths: AppPaths) -> Path | None:
    """TLC's timestamped folder in the one run folder, once TLC has made it: the moment a test may signal (52)."""
    for folder in run_folders(paths):
        made = sorted(entry for entry in folder.iterdir() if entry.is_dir())
        if made:
            return made[0]
    return None


@dataclass
class Running:
    """tlaup started as a real process with SIGINT at its default (T5), stdout and stderr going to files."""

    process: subprocess.Popen[bytes]
    stdout_file: Path
    stderr_file: Path

    @property
    def pid(self) -> int:
        return self.process.pid

    def ended(self) -> bool:
        return self.process.poll() is not None

    def send(self, number: int) -> None:
        """To the tlaup process alone, not its group (11 R2: the signal goes to tlaup)."""
        os.kill(self.process.pid, number)

    def stdout(self) -> str:
        return self.stdout_file.read_bytes().decode("utf-8", "replace")

    def stderr(self) -> str:
        return self.stderr_file.read_bytes().decode("utf-8", "replace")

    def output(self) -> str:
        return f"\n--- stdout ---\n{self.stdout()}\n--- stderr ---\n{self.stderr()}"

    def wait(self, *, timeout: float = PROCESS_SECONDS) -> int:
        """The exit code as a shell reports it; a tlaup still running after ``timeout`` is killed and the test fails."""
        try:
            self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.kill()
            message = f"tlaup was still running after {timeout} s; it and its JVM were killed{self.output()}"
            raise AssertionError(message) from None
        return exit_code_of(self.process.returncode)

    def kill(self) -> None:
        """SIGKILL tlaup, then by process id the processes it started, found first: once tlaup is gone, ``pgrep -P``
        no longer finds them, and a JVM whose lifeline has not yet fired would run on."""
        children = java_children(self.pid) if self.process.poll() is None else []
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        kill_pids(children)

    def jvm(self, paths: AppPaths) -> list[int]:
        """Once TLC has made its folder under the run folder: the processes tlaup started, by ``pgrep -P``."""
        wait_until(lambda: tlc_folder(paths), what="TLC's folder under the run folder", ended=self.ended)
        return wait_until(lambda: java_children(self.pid), what="the JVM tlaup started", ended=self.ended)


def start_tlaup(args: Sequence[str], folder: Path, *, prefix: Sequence[str] = ()) -> Running:
    """``[prefix...] python -m tlaup ARGS`` in the working folder, stdin the null device, output into ``folder``."""
    folder.mkdir(parents=True, exist_ok=True)
    stdout_file, stderr_file = folder / "stdout", folder / "stderr"
    with stdout_file.open("wb") as out, stderr_file.open("wb") as err:
        process = start(
            [*prefix, sys.executable, "-m", "tlaup", *args], stdin=subprocess.DEVNULL, stdout=out, stderr=err
        )
    return Running(process, stdout_file, stderr_file)


@dataclass
class Reaper:
    """What a test started: at its end, whatever the outcome, every tlaup still alive is killed together with the
    processes it started at that moment, and every JVM the test noted with ``watch``, all by process id."""

    started: list[Running] = field(default_factory=list)
    pids: list[int] = field(default_factory=list)

    def start(self, args: Sequence[str], folder: Path, *, prefix: Sequence[str] = ()) -> Running:
        running = start_tlaup(args, folder, prefix=prefix)
        self.started.append(running)
        return running

    def watch(self, pids: Sequence[int]) -> list[int]:
        self.pids.extend(pids)
        return list(pids)

    def reap(self) -> None:
        """Each tlaup with the processes it started now (``Running.kill``), then every JVM a test noted earlier."""
        for running in self.started:
            running.kill()
        kill_pids(self.pids)


def kill_pids(pids: Sequence[int]) -> None:
    """SIGKILL, by process id, each of ``pids`` still alive, and wait for them to be gone.

    Not guarded against a reused process id: a JVM that ended long before its id is killed could in principle have
    handed the id to an unrelated process. Accepted: the ids are a few seconds old at most, and the system hands
    them out in rising order on Linux.
    """
    for pid in pids:
        if alive(pid):
            with contextlib.suppress(ProcessLookupError):
                os.kill(pid, signal.SIGKILL)
    still_alive(pids)
