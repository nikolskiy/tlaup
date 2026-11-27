"""`signals_held`, each case in a child Python process so that the test runner's own dispositions are untouched
(design 20 G3, 21 S3). Each child prints what it saw as JSON on its last line; the test kills it by process id if it
has not ended."""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import threading
import time
from typing import TYPE_CHECKING, Any

import pytest

from tlaup.errors import InternalError
from tlaup.java.launcher import signals_held

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="needs POSIX signals")

PRELUDE = """
import json, os, signal, sys, time
from pathlib import Path
from tlaup.java.launcher import JavaInvocation, run_passthrough, signals_held
def report(**seen):
    print(json.dumps(seen), flush=True)
"""

# Stands for java in a passthrough run: says it is ready, notes a SIGTERM and ends with 5, ends by itself with 7
# once the release file exists.
STAND_IN = """#!{python}
import signal, sys, time
from pathlib import Path
ready, release = Path(sys.argv[-2]), Path(sys.argv[-1])
def term(*_):
    Path(str(ready) + ".term").write_text("term")
    sys.exit(5)
signal.signal(signal.SIGTERM, term)
ready.write_text("ready")
while not release.exists():
    time.sleep(0.01)
sys.exit(7)
"""


def wait_until(condition: Callable[[], bool], what: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting until {what}"
        time.sleep(0.005)


def run_child(
    code: str, *args: str, timeout: float = 30, during: Callable[[subprocess.Popen[str]], None] | None = None
) -> dict[str, Any]:
    """Runs PRELUDE + code in a child Python with `args`; `during(process)` runs while it does. Returns its report."""
    child = subprocess.Popen(
        [sys.executable, "-c", PRELUDE + code, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        if during is not None:
            during(child)
        out, err = child.communicate(timeout=timeout)
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()
    assert child.returncode == 0, f"the child ended with {child.returncode}: {err}"
    return dict(json.loads(out.strip().splitlines()[-1]))


def stand_in(tmp_path: Path) -> Path:
    script = tmp_path / "stand-in-java"
    script.write_text(STAND_IN.format(python=sys.executable), encoding="utf-8")
    script.chmod(0o755)
    return script


def test_a_signal_ignored_on_entry_gets_no_handler_and_stays_ignored() -> None:
    seen = run_child("""
signal.signal(signal.SIGHUP, signal.SIG_IGN)  # as nohup starts it
with signals_held() as signals:
    inside = signal.getsignal(signal.SIGHUP) == signal.SIG_IGN
    os.kill(os.getpid(), signal.SIGHUP)
    first, count = signals.first, signals.count
report(inside=inside, first=first, count=count, after=signal.getsignal(signal.SIGHUP) == signal.SIG_IGN)
""")
    assert seen == {"inside": True, "first": None, "count": 0, "after": True}


def test_the_handlers_are_python_functions_and_are_restored() -> None:
    seen = run_child("""
names = ("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT")
before = {name: signal.getsignal(getattr(signal, name)) for name in names}
with signals_held():
    inside = {name: callable(signal.getsignal(getattr(signal, name))) for name in names}
restored = {name: signal.getsignal(getattr(signal, name)) == before[name] for name in names}
report(inside=inside, restored=restored)
""")
    assert seen["inside"] == dict.fromkeys(("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT"), True)
    assert seen["restored"] == dict.fromkeys(("SIGINT", "SIGTERM", "SIGHUP", "SIGQUIT"), True)


def test_sigquit_inside_the_block_changes_nothing() -> None:
    seen = run_child("""
with signals_held() as signals:
    os.kill(os.getpid(), signal.SIGQUIT)
    state = [signals.first, signals.count, signals.held, signals.first_at]
report(state=state)
""")
    assert seen == {"state": [None, 0, False, None]}


LEFT_TO_THE_CHILD = """
script, ready, release, marker = (Path(arg) for arg in sys.argv[1:5])
then_term = sys.argv[5] == "term"
inv = JavaInvocation(java=script, jvm_options=(), system_properties=(), classpath=(), main_class="Repl",
                     args=(str(ready), str(release)))
with signals_held(leave_interrupt=True) as signals:
    os.kill(os.getpid(), signal.SIGINT)  # before any child exists
    before = [signals.first, signals.count]
    handler = signal.getsignal(signal.SIGINT)
    def noted(number, frame):  # the launcher's handler, then a note for the test
        handler(number, frame)
        marker.write_text("handled")
    signal.signal(signal.SIGINT, noted)
    outcome = run_passthrough(inv, signals=signals, forward_interrupt=False)
    during = [signals.first, signals.count]
report(before=before, during=during, code=outcome.exit_code, tool=outcome.tool_exit_code,
       stopped_by=outcome.stopped_by, term=Path(str(ready) + ".term").exists())
"""


@pytest.mark.parametrize("then", ["ends", "term"])
def test_a_sigint_left_to_the_child_is_not_recorded(tmp_path: Path, then: str) -> None:
    ready, release, marker = tmp_path / "ready", tmp_path / "release", tmp_path / "handled"

    def while_it_runs(child: subprocess.Popen[str]) -> None:
        wait_until(ready.exists, "the stand-in has started")
        child.send_signal(signal.SIGINT)  # to tlaup alone, while the child runs
        wait_until(marker.exists, "the SIGINT was handled")
        if then == "term":
            child.send_signal(signal.SIGTERM)
        else:
            release.write_text("go")

    args = (str(stand_in(tmp_path)), str(ready), str(release), str(marker), then)
    seen = run_child(LEFT_TO_THE_CHILD, *args, during=while_it_runs)
    if then == "ends":  # the child's own code, not 130
        expected = {"during": [None, 0], "code": 7, "tool": 7, "stopped_by": None, "term": False}
    else:  # the SIGTERM is the first signal: terminate(), not kill()
        expected = {"during": ["term", 1], "code": 143, "tool": 5, "stopped_by": "term", "term": True}
    assert seen == {"before": [None, 0], **expected}


def test_signals_held_off_the_main_thread_is_an_internal_error() -> None:
    raised: list[BaseException] = []

    def enter() -> None:
        try:
            with signals_held():
                pass
        except InternalError as error:
            raised.append(error)

    before = {number: signal.getsignal(number) for number in (signal.SIGINT, signal.SIGTERM)}
    worker = threading.Thread(target=enter)
    worker.start()
    worker.join(timeout=10)
    assert len(raised) == 1
    assert {number: signal.getsignal(number) for number in before} == before
