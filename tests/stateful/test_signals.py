"""Stateful property test of the launcher's signal handling (design 20 G3, 11 R2): the mirror of specs/Signals.tla.

The one tlaup process of the spec is the test process itself. It enters ``signals_held``,
runs one child a step at a time, and sends itself real signals between the steps. Each
action of the spec is a rule with the action's enabling condition as its precondition; the
properties are checked on the real handlers, the real ``Signals`` object and the real child.

What differs from the spec, and why:

- A signal is sent only where the spec has tlaup alive under its handlers. Before sending,
  the rule looks at the handler that is installed: Python's default there is a failure of
  ``NoDefaultHandler``, reported without sending the signal, which would end the test run.
- After a ``terminate()`` or ``kill()`` the machine waits until the child has gone, so the
  child's exit follows at once instead of at any later moment. A step is then repeatable.
- The grace period runs on an injected clock.
- The parser's checkpoint mark (2195, then 2196) is two rules that call
  ``checkpoint_started`` and ``checkpoint_written``, in a parsed (streaming) run only; the
  line tlaup prints while it holds a signal is the runner's and is not checked here.
- ``TlaupDies`` cannot be a rule: the test process is the tlaup of the spec and cannot be
  killed and go on. The real lifeline is a Java agent, which a fake ``java`` cannot carry,
  so ``ChildEndsWithTlaup`` is not checked here. It rests on the lifeline job's test of the
  agent with a real JVM (package 06), the unit test that ``argv()`` puts the agent first with
  tlaup's process id, and the integration test that a killed tlaup leaves no ``java``.
- SIGQUIT is never recorded. The fake child notes it and carries on, as a JVM does after its
  thread dump; a streaming run's attached child must note it (the launcher forwards it, D60),
  a passthrough run's child must not (question Q5).

Revised 2026-11-20 for decisions D51 and D52 (the spec's ``Defer`` and ``Lifeline`` both on).

The machine runs against ``tlaup.java.launcher`` (package 21). The throwaway model it ran
against before the launcher existed, ``reference_launcher.py``, was deleted with its tests.
"""

from __future__ import annotations

import importlib
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

pytest.importorskip("hypothesis")

from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import (
    RuleBasedStateMachine,
    initialize,
    invariant,
    precondition,
    rule,
    run_state_machine_as_test,
)

pytestmark = pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="needs POSIX signals")

PROJECT_ROOT = Path(__file__).parents[2]
GRACE = 10.0
OWN_CODE = 7
CODES = {"int": 130, "term": 143, "hup": 129}
HELD = {"held", "checked", "spawning", "attached", "reaped", "summary"}
ORDER = ["before", "held", "checked", "spawning", "attached", "reaped", "summary", "left"]

# Stands for java: it ends with OWN_CODE when told to (SIGUSR1), and in mode "stubborn"
# it does not end on SIGTERM but notes that it got one. A SIGQUIT it notes and carries on,
# as a JVM does after its thread dump (question Q5).
FAKE_CHILD = """#!{python}
import signal, sys, time
from pathlib import Path
mode, ready = sys.argv[-2], sys.argv[-1]
def noted(*_):
    with Path(ready + ".quit").open("a") as note:
        note.write("quit\\n")
if mode == "stubborn":
    signal.signal(signal.SIGTERM, lambda *_: Path(ready + ".term").write_text("term"))
signal.signal(signal.SIGQUIT, noted)
signal.signal(signal.SIGUSR1, lambda *_: sys.exit({code}))
Path(ready).write_text("ready")
while True:
    time.sleep(0.02)
"""


def numbers() -> dict[str, int]:
    return {"int": signal.SIGINT, "term": signal.SIGTERM, "hup": signal.SIGHUP, "quit": signal.SIGQUIT}


def tlaup_impl() -> SimpleNamespace:
    launcher = importlib.import_module("tlaup.java.launcher")

    def child_run(script: Path, mode: str, ready: Path, signals: Any, **options: Any) -> Any:
        invocation = launcher.JavaInvocation(
            java=script, jvm_options=(), system_properties=(), classpath=(), main_class="Fake", args=(mode, str(ready))
        )
        return launcher.ChildRun(invocation, signals, **options)

    return SimpleNamespace(name=launcher.__name__, signals_held=launcher.signals_held, child_run=child_run)


def gone(pid: int) -> bool:
    """The child has ended; it is not reaped here, so the launcher still has to see it."""
    try:
        return os.waitid(os.P_PID, pid, os.WEXITED | os.WNOWAIT | os.WNOHANG) is not None
    except ChildProcessError:
        return True


def wait_until(condition: Any, what: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting until {what}"
        time.sleep(0.002)


def ignored_by(pid: int) -> set[int] | None:
    """The signals a process ignores, from /proc; None where there is no /proc."""
    try:
        status = Path(f"/proc/{pid}/status").read_text(encoding="ascii")
    except OSError:
        return None
    found = re.search(r"^SigIgn:\s*([0-9a-f]+)", status, re.MULTILINE)
    if found is None:
        return None
    mask = int(found.group(1), 16)
    return {number for number in range(1, 65) if mask & (1 << (number - 1))}


class SignalsMachine(RuleBasedStateMachine):
    impl: SimpleNamespace
    base: Path

    def __init__(self) -> None:
        super().__init__()
        self.root = Path(tempfile.mkdtemp(dir=self.base))
        self.script = self.root / "fake-java"
        self.script.write_text(FAKE_CHILD.format(python=sys.executable, code=OWN_CODE), encoding="utf-8")
        self.script.chmod(0o755)
        self.original = {number: signal.getsignal(number) for number in numbers().values()}
        self.now = 1000.0
        self.clock_runs = False
        self.phase = "before"
        self.ignored: set[str] = set()
        self.leave = self.stubborn = self.streaming = self.loop_will_fail = False
        self.quiet_until = "held"
        self.manager: Any = None
        self.signals: Any = None
        self.run: Any = None
        self.outcome: Any = None
        self.first: str | None = None
        self.count = 0
        self.child = "none"
        self.terminated = self.killed = False
        self.first_before_exit = False
        self.checkpointing = self.held = False

    def clock(self) -> float:
        if self.clock_runs:
            self.now += GRACE
        return self.now

    def teardown(self) -> None:
        try:
            if self.run is not None and self.run.pid is not None:
                if not gone(self.run.pid):
                    os.kill(self.run.pid, signal.SIGKILL)
                    wait_until(lambda: gone(self.run.pid), "the child has gone")
                for _ in range(200):  # the launcher's own loop reaps the child and closes its pipe
                    if self.run.turn(timeout=0.05):
                        break
            if self.manager is not None and self.phase in HELD:
                self.manager.__exit__(None, None, None)
        finally:
            for number, handler in self.original.items():
                signal.signal(number, handler)

    @initialize(
        ignored=st.one_of(st.just(set()), st.sets(st.sampled_from(["int", "term", "hup", "quit"]), max_size=2)),
        leave=st.booleans(),
        stubborn=st.booleans(),
        streaming=st.booleans(),
        loop_will_fail=st.sampled_from([False, False, False, True]),
        quiet_until=st.sampled_from(sorted(HELD, key=ORDER.index)),
    )
    def how_tlaup_was_started(
        self, ignored: set[str], leave: bool, stubborn: bool, streaming: bool, loop_will_fail: bool, quiet_until: str
    ) -> None:
        """Draw the things the spec chooses at the start, and the phase the first signal waits for.

        Without the last one a signal nearly always lands early, and the examples where the
        first one lands after the child has gone, the ones two properties are about, are rare.
        """
        self.quiet_until = quiet_until
        if ORDER.index(quiet_until) > ORDER.index("attached"):  # the child must end by itself to get there
            stubborn, loop_will_fail = False, False
            ignored = ignored - {"term"}
        self.ignored, self.leave, self.stubborn, self.loop_will_fail = ignored, leave, stubborn, loop_will_fail
        self.streaming = streaming and not leave  # only a passthrough run leaves Ctrl-C to the child
        for name in ignored:  # nohup, or a background job of a shell script
            signal.signal(numbers()[name], signal.SIG_IGN)

    def quits_noted(self) -> int:
        note = self.root / "ready.quit"
        return len(note.read_text(encoding="utf-8").splitlines()) if note.exists() else 0

    def needs_kill(self) -> bool:
        """SIGTERM does not end this child: it ignores it itself, or inherited the ignore."""
        return self.stubborn or "term" in self.ignored

    def child_was_stopped(self, *, killed: bool) -> None:
        if killed:
            self.killed = True
        else:
            self.terminated = True
        if killed or not self.needs_kill():
            wait_until(lambda: gone(self.run.pid), "the child has gone")
            self.child = "exited"
            self.first_before_exit = self.first is not None
        elif self.stubborn:
            wait_until((self.root / "ready.term").exists, "the child got SIGTERM")

    # ------------------------------------------------------------------ the launcher

    @precondition(lambda self: self.phase == "before")
    @rule()
    def enter(self) -> None:
        self.manager = self.impl.signals_held(leave_interrupt=self.leave, clock=self.clock)
        self.signals = self.manager.__enter__()
        self.phase = "held"

    @precondition(lambda self: self.phase == "held")
    @rule()
    def check(self) -> None:
        self.run = self.impl.child_run(
            self.script,
            "stubborn" if self.stubborn else "plain",
            self.root / "ready",
            self.signals,
            passthrough=not self.streaming,
            grace_seconds=GRACE,
            clock=self.clock,
        )
        may_start = self.run.may_start()
        assert may_start == (self.first is None), "NothingStartsAfterSeenSignal: may_start disagrees with Signals"
        if may_start:
            self.phase = "checked"
        else:
            self.outcome = self.run.outcome()
            assert self.outcome.stopped_by == self.first
            assert self.outcome.exit_code == CODES[self.first]
            self.phase = "reaped"

    @precondition(lambda self: self.phase == "checked")
    @rule()
    def spawn(self) -> None:
        self.run.spawn()
        wait_until((self.root / "ready").exists, "the child is ready")
        self.child = "running"
        ignores = ignored_by(self.run.pid)
        if ignores is not None:
            for name in ("int", "hup"):
                inherited = numbers()[name] in ignores
                assert inherited == (name in self.ignored), f"IgnoredStaysIgnored: the child and SIG{name.upper()}"
        self.phase = "spawning"

    @precondition(lambda self: self.phase == "spawning")
    @rule()
    def attach(self) -> None:
        self.run.attach()
        self.phase = "attached"
        if self.first is not None and self.child == "running":
            self.child_was_stopped(killed=False)

    @precondition(lambda self: self.phase == "attached" and self.child == "running")
    @rule()
    def turn_with_nothing_to_do(self) -> None:
        assert self.run.turn(timeout=0.01) is False, "the loop ended while the child runs"

    @precondition(lambda self: self.phase == "attached" and self.child == "running" and self.terminated)
    @rule()
    def grace_period_runs_out(self) -> None:
        self.now += GRACE + 1
        self.run.turn(timeout=0.01)
        self.child_was_stopped(killed=True)

    @precondition(lambda self: self.phase == "attached" and self.loop_will_fail)
    @rule()
    def loop_fails(self) -> None:
        """on_stdout raised: the finally round the loop stops the child."""
        self.clock_runs = True
        try:
            self.run.stop()
        finally:
            self.clock_runs = False
        assert gone(self.run.pid), "ChildNeverOrphaned: the child runs on after the loop failed"
        self.child = "exited"
        self.outcome = None
        self.phase = "summary"

    @precondition(lambda self: self.phase == "attached" and self.child == "exited")
    @rule()
    def reap(self) -> None:
        for _ in range(200):
            if self.run.turn(timeout=0.05):
                break
        else:
            pytest.fail("the loop did not end after the child had gone")
        self.outcome = self.run.outcome()
        assert self.outcome.stopped_by == self.first, "ExitCodeAsSeen: stopped_by is not Signals.first"
        expected = CODES[self.first] if self.first else OWN_CODE
        assert self.outcome.exit_code == expected, f"ExitCodeAsSeen: {self.outcome.exit_code}, expected {expected}"
        if self.first_before_exit:
            assert self.outcome.exit_code == CODES[self.first], "SignalNeverLost"
        self.phase = "reaped"

    @precondition(lambda self: self.phase == "reaped")
    @rule()
    def summary(self) -> None:
        assert self.run.outcome() == self.outcome, "LateSignalChangesNothing: the outcome changed"
        self.phase = "summary"

    @precondition(lambda self: self.phase == "summary")
    @rule()
    def leave_the_block(self) -> None:
        if self.outcome is not None:
            assert self.run.outcome() == self.outcome, "LateSignalChangesNothing: the outcome changed"
        self.manager.__exit__(None, None, None)
        self.phase = "left"
        for name, number in numbers().items():
            expected = signal.SIG_IGN if name in self.ignored else self.original[number]
            assert signal.getsignal(number) == expected, f"SIG{name.upper()} was not restored"
        if self.run is not None and self.run.pid is not None:
            assert gone(self.run.pid), "ChildNeverOrphaned: tlaup leaves while the child runs"

    @precondition(lambda self: self.phase == "left")
    @rule()
    def exited(self) -> None:
        """tlaup has left the block: nothing more happens in this model."""

    @precondition(
        lambda self: self.phase == "attached" and self.streaming and self.child == "running" and not self.checkpointing
    )
    @rule()
    def checkpoint_started(self) -> None:
        """The parser has read 2195: TLC writes a checkpoint (a parsed run only)."""
        self.signals.checkpoint_started()
        self.checkpointing = True

    @precondition(lambda self: self.phase == "attached" and self.held and self.child == "running")
    @rule()
    def a_long_checkpoint(self) -> None:
        """Finding FC7 of the 2026-11-20 review: the grace period runs from the moment the
        signal is sent on, so time passing while it is held must not kill the child."""
        self.now += GRACE + 1
        self.run.turn(timeout=0.01)
        time.sleep(0.05)
        assert not gone(self.run.pid), "the grace period ran from the held signal's arrival and killed the child"
        assert not (self.root / "ready.term").exists(), "the child got SIGTERM while the signal was held"

    @precondition(lambda self: self.phase == "attached" and self.checkpointing)
    @rule()
    def checkpoint_written(self) -> None:
        """The parser has read 2196: a first signal held meanwhile is sent on now (D52)."""
        self.signals.checkpoint_written()
        self.checkpointing = False
        if self.held:
            self.held = False
            if self.child == "running":
                self.child_was_stopped(killed=False)

    # ------------------------------------------------------------------ the child and the signals

    @precondition(lambda self: self.child == "running" and not self.needs_kill())
    @rule()
    def child_ends_by_itself(self) -> None:
        os.kill(self.run.pid, signal.SIGUSR1)
        wait_until(lambda: gone(self.run.pid), "the child has gone")
        self.child = "exited"
        self.first_before_exit = self.first is not None

    @precondition(lambda self: self.phase in HELD and ORDER.index(self.phase) >= ORDER.index(self.quiet_until))
    @rule(name=st.sampled_from(["int", "term", "hup", "int", "term", "hup", "quit"]))
    def signal_arrives(self, name: str) -> None:
        number = numbers()[name]
        handler = signal.getsignal(number)
        if name in self.ignored:
            assert handler == signal.SIG_IGN, f"IgnoredStaysIgnored: SIG{name.upper()} got a handler"
        else:
            ours = callable(handler) and handler is not signal.default_int_handler
            assert ours, f"NoDefaultHandler: SIG{name.upper()} would reach Python's default handler"
        quits = self.quits_noted()
        os.kill(os.getpid(), number)  # the handler has run when this returns
        if name == "quit" and name not in self.ignored and self.child == "running":
            if self.streaming and self.phase == "attached":  # D60: sent on to the JVM of a parsed run
                wait_until(lambda: self.quits_noted() == quits + 1, "SIGQUIT reached the child of a streaming run")
            elif not self.streaming:  # the terminal has already sent it to a child in tlaup's group
                time.sleep(0.05)
                assert self.quits_noted() == quits, "SIGQUIT was sent on to the child of a passthrough run"
        if name in self.ignored or name == "quit" or (name == "int" and self.leave):
            return
        self.count += 1
        if self.first is None:
            self.first = name
        if self.phase == "attached" and self.child == "running":
            if self.count == 1 and self.checkpointing:  # FirstSignalWaitsForCheckpoint
                self.held = True
                time.sleep(0.05)
                assert not gone(self.run.pid), "FirstSignalWaitsForCheckpoint: the child ended at a held signal"
                assert not (self.root / "ready.term").exists(), "FirstSignalWaitsForCheckpoint: SIGTERM was sent"
            else:
                self.held = False
                self.child_was_stopped(killed=self.count > 1)

    # ------------------------------------------------------------------ the properties

    @invariant()
    def signals_object_agrees(self) -> None:
        if self.signals is not None and self.phase in HELD:
            assert self.signals.first == self.first, f"Signals.first is {self.signals.first}, expected {self.first}"
            assert self.signals.count == self.count, f"Signals.count is {self.signals.count}, expected {self.count}"
            assert self.signals.held == self.held, f"Signals.held is {self.signals.held}, expected {self.held}"

    @invariant()
    def a_signal_reaches_the_child(self) -> None:
        if self.phase == "attached" and self.first is not None and self.child == "running" and not self.held:
            assert self.terminated or self.killed, "SignalReachesChild"
            assert self.needs_kill(), "SignalReachesChild: a child that heeds SIGTERM runs on after it"


def run_machine(impl: SimpleNamespace, base: Path) -> None:
    machine = type("Signals", (SignalsMachine,), {"impl": impl, "base": base})
    run_state_machine_as_test(machine, settings=settings(stateful_step_count=30))


def test_signals_machine(tmp_path: Path) -> None:
    run_machine(tlaup_impl(), tmp_path)


# The machine sends signals from inside the process and relies on the handler having run
# when os.kill returns. A second Python process confirms that a signal from outside is
# recorded the same way.

CHILD = """
import importlib, sys
sys.path.insert(0, sys.argv[1])
impl = getattr(importlib.import_module("tests.stateful.test_signals"), sys.argv[2])()
with impl.signals_held() as signals:
    print("ready", flush=True)
    sys.stdin.readline()
    print(signals.first, signals.count, flush=True)
"""


def signal_from_outside_agrees(impl: SimpleNamespace, impl_name: str) -> None:
    before = signal.getsignal(signal.SIGTERM)
    try:
        with impl.signals_held() as signals:
            os.kill(os.getpid(), signal.SIGTERM)
            inside = (signals.first, signals.count)
    finally:
        signal.signal(signal.SIGTERM, before)
    assert inside == ("term", 1), "the handler had not run when os.kill returned"

    argv = [sys.executable, "-c", CHILD, str(PROJECT_ROOT), impl_name]
    other = subprocess.Popen(argv, cwd=PROJECT_ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert other.stdout is not None
        assert other.stdout.readline().strip() == "ready"
        other.send_signal(signal.SIGTERM)
    finally:
        answer = other.communicate("\n", timeout=30)[0]
    assert answer.split() == ["term", "1"], f"a signal from outside was recorded as {answer!r}"
    assert other.returncode == 0, "the process did not survive a SIGTERM under signals_held"


def test_a_signal_from_this_process_stands_for_one_from_outside() -> None:
    signal_from_outside_agrees(tlaup_impl(), "tlaup_impl")
