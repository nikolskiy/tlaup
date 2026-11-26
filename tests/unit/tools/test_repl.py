"""`run_repl`: a Ctrl-C is left to the REPL and is not recorded (design 21 S3, 20 G3).

Each case runs `run_repl` in a child Python process with stdin on the null device, so that the test runner's own
signal dispositions are not touched, as the `signals_held` tests do. A stand-in for java is the child's child; the
test waits for its ready file before it signals, and sends signals to the Python child alone, never to its group.
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

pytestmark = pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="needs POSIX signals")

# Stands for java: says it is ready, notes a SIGINT and a SIGTERM, ends with 5 on SIGTERM and with 7 once the
# release file exists.
STAND_IN = """#!{python}
import signal, sys, time
from pathlib import Path
ready, release = Path(sys.argv[-2]), Path(sys.argv[-1])
def note(name):
    def handler(*_):
        Path(str(ready) + "." + name).write_text(name)
        if name == "term":
            sys.exit(5)
    return handler
signal.signal(signal.SIGINT, note("int"))
signal.signal(signal.SIGTERM, note("term"))
ready.write_text("ready")
while not release.exists():
    time.sleep(0.01)
sys.exit(7)
"""

CHILD = """
import json, os, sys
from pathlib import Path
from tlaup.java.launcher import JavaInvocation
from tlaup.tools.repl import run_repl
script, ready, release = (Path(arg) for arg in sys.argv[1:4])
inv = JavaInvocation(java=script, jvm_options=(), system_properties=(), classpath=(), main_class="tlc2.REPL",
                     args=(str(ready), str(release)))
outcome = run_repl(inv)
print(json.dumps({"code": outcome.exit_code, "tool": outcome.tool_exit_code, "stopped_by": outcome.stopped_by}),
      flush=True)
"""


def wait_until(condition: Callable[[], bool], what: str, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        assert time.monotonic() < deadline, f"timed out waiting until {what}"
        time.sleep(0.005)


def run_repl_child(tmp_path: Path, *, then: str) -> dict[str, object]:
    script = tmp_path / "stand-in-java"
    script.write_text(STAND_IN.format(python=sys.executable), encoding="utf-8")
    script.chmod(0o755)
    ready, release = tmp_path / "ready", tmp_path / "release"
    child = subprocess.Popen(
        [sys.executable, "-c", CHILD, str(script), str(ready), str(release)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_until(ready.exists, "the stand-in has started")
        child.send_signal(signal.SIGINT)  # to the Python process alone, while the stand-in runs
        time.sleep(0.3)  # the handler runs at once; give a wrongly forwarded signal time to arrive
        if then == "term":
            child.send_signal(signal.SIGTERM)
        else:
            release.write_text("go")
        out, err = child.communicate(timeout=30)
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate()
    assert child.returncode == 0, f"the child ended with {child.returncode}: {err}"
    report: dict[str, object] = json.loads(out.strip().splitlines()[-1])
    return report


def test_a_sigint_reaches_nobody_and_the_repls_own_code_is_kept(tmp_path: Path) -> None:
    seen = run_repl_child(tmp_path, then="ends")
    assert seen == {"code": 7, "tool": 7, "stopped_by": None}  # not 130
    assert not (tmp_path / "ready.int").exists()  # the stand-in logged no signal
    assert not (tmp_path / "ready.term").exists()


def test_a_sigint_and_then_a_sigterm_gives_the_stand_in_a_sigterm_and_143(tmp_path: Path) -> None:
    seen = run_repl_child(tmp_path, then="term")
    assert seen == {"code": 143, "tool": 5, "stopped_by": "term"}
    assert (tmp_path / "ready.term").exists()  # terminate(), not kill()
    assert not (tmp_path / "ready.int").exists()
