"""The REPL on a pseudo-terminal, its JVM carrying the lifeline agent (design 20 G3, last sentence of "The lifeline,
with a real JVM"; 30 I2; package 52).

The agent must not take stdin from the REPL: ``1+1`` typed into the terminal still shows ``2``. The jar comes from
``TLAUP_TEST_JARS``, found as the integration tests find theirs (``tests/integration/discovery.py``), and is copied
into a store under this test's own ``TLAUP_HOME``; with no build that has the REPL the test is skipped with the reason.
"""

from __future__ import annotations

import os
import shlex
import sys
import time
from pathlib import Path

import pytest

from tests.integration.discovery import REMOVED_VARIABLES, VARIABLE, find_test_jars, install, missing
from tests.steps._terminal import TerminalRun, run_on_terminal
from tlaup.paths import AppPaths

SIZE = (100, 30)
EOF = "\x04"  # Ctrl-D: end of input on the terminal, which ends the REPL
WAIT_SECONDS = 60.0
EOF_TRIES, EOF_SECONDS = 5, 5.0


def test_repl_reads_the_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reason = missing(os.environ)
    if reason is not None:
        pytest.skip(f"the REPL case needs a jar with the REPL from {VARIABLE}: {reason}")
    jars = [jar for jar in find_test_jars(Path(os.environ[VARIABLE])) if "repl" in jar.info.capabilities]
    if not jars:
        pytest.skip(f"{VARIABLE} holds no build with the REPL (a rolling build has it)")
    for name in list(os.environ):
        if name.startswith("TLAUP_"):
            monkeypatch.delenv(name)
    for name in REMOVED_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    home, jvm = tmp_path / "home", tmp_path / "jvm"
    for folder in (home, jvm / "home", jvm / "tmp"):
        folder.mkdir(parents=True)
    monkeypatch.setenv("TLAUP_HOME", str(tmp_path / "tlaup"))  # apart from HOME, so HOME must stay empty
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TLAUP_TOOL_REPOSITORY", "https://127.0.0.1:9/repos/tlaplus/tlaplus")  # no network
    options = [f"-Duser.home={jvm / 'home'}", f"-Djava.io.tmpdir={jvm / 'tmp'}"]  # the JVM's own folders (01 T9)
    monkeypatch.setenv("TLAUP_JAVA_OPTS", shlex.join(options))
    monkeypatch.chdir(tmp_path)
    install(AppPaths.from_env(os.environ), jars[0])

    run = run_on_terminal([sys.executable, "-m", "tlaup", "repl"], size=SIZE)
    try:
        run.pump_until(lambda: run.ended or bool(_lines(run.screen)), timeout=WAIT_SECONDS, what="the REPL's banner")
        run.type("1+1\n")
        run.pump_until(lambda: "2" in _answers(run.screen), timeout=WAIT_SECONDS, what="the value 2 on the terminal")
        _end_input(run)
        outcome = run.finish(timeout=WAIT_SECONDS)
    except BaseException:
        run.kill()
        run.close()
        raise
    assert outcome.exit_code == 0, outcome.stdout
    assert not any(home.iterdir()), sorted(home.rglob("*"))  # user.home is moved (01 T9)


def _end_input(run: TerminalRun) -> None:
    """Ctrl-D, sent again while the REPL has not ended: one that arrives while the line editor is switching the
    terminal's mode can be lost (seen once in two tries on Linux, 2026-11-26)."""
    for _ in range(EOF_TRIES):
        run.type(EOF)
        deadline = time.monotonic() + EOF_SECONDS
        while not run.ended and time.monotonic() < deadline:
            run.read()
        if run.ended:
            return


def _lines(screen: object) -> list[str]:
    return [line.rstrip() for line in screen.display if line.strip()]  # type: ignore[attr-defined]


def _answers(screen: object) -> list[str]:
    """The last word of each line after the one that holds the typed ``1+1``: the REPL prints the value there."""
    lines = _lines(screen)
    typed = [index for index, line in enumerate(lines) if line.endswith("1+1")]
    if not typed:
        return []
    return [line.split()[-1] for line in lines[typed[0] + 1 :] if line.split()]
