"""Running the real tools from the integration tests: through the Python API, and tlaup as a real process (01 T9).

The API forms are the ones T9 names (``run_tlc`` with a ``CollectingReporter``, ``run_sany``, ``run_pcal``), driven
through the same preflight the commands use; the real-process form is for a command that passes the terminal through
or a signal that must reach a process (T5's situations 1 and 3). Every function reads the environment the isolation
fixture built, as the commands would.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from tests.parse.facts import facts_for
from tests.steps._process import exit_code_of, start
from tlaup.config.loader import load_settings
from tlaup.reporters.collecting import CollectingReporter
from tlaup.tlc.command import build_tlc_command
from tlaup.tlc.invocation import TlcRequest, resolve_tlc_invocation
from tlaup.tlc.runner import RunOutcome, run_tlc
from tlaup.tools.invocation import ToolInvocation, build_tool_command, resolve_tool_invocation
from tlaup.tools.pcal import PcalOutcome, run_pcal
from tlaup.tools.sany import SanyOutcome, run_sany

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tlaup.java.launcher import JavaInvocation
    from tlaup.paths import AppPaths
    from tlaup.versioning.store import Build
    from tlaup_parse import Diagnostic, RunResult

REPO = Path(__file__).resolve().parents[2]
SPECS = Path(__file__).resolve().parent / "specs"  # the inputs no golden spec provides
EXAMPLES = REPO / "docs" / "examples"
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
    outcome = run_tlc(inv, build_tlc_command(inv), reporter, paths=paths, now=utc_now, notice=notices.append)
    return Live(outcome, reporter, notices)


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
