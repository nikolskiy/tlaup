"""Completion in the real shells (design 23 C3; package 52): bash runs the script, zsh and fish check its syntax.

Linux only (the integration job's Linux cell). No shell start-up file is read or written: bash runs with
``--norc --noprofile``, zsh with ``-f``, fish with ``--no-config``, and each gets the script as a variable or as a
file in the test's own folder.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from tests.integration.live import run_tlaup
from tlaup.versioning.spec import format_build

if TYPE_CHECKING:
    from pathlib import Path

    from tlaup.versioning.store import Build

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="the completion checks run on Linux only")

SHELL_SECONDS = 60.0


def completion_script(shell: str) -> str:
    done = run_tlaup(["completion", shell])
    assert done.exit_code == 0, done.stderr
    return done.stdout


def test_bash(live_build: Build, tmp_path: Path) -> None:
    """The bash script, sourced in a non-interactive bash, completes ``tlaup tool pin `` with the installed build:
    its function is called as bash calls it, with ``COMP_WORDS`` and ``COMP_CWORD`` set and the command's name."""
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash is not on PATH")
    shim = tmp_path / "bin" / "tlaup"  # the script calls `tlaup` back by name, as an installed tlaup would be
    shim.parent.mkdir()
    shim.write_text(f'#!/bin/sh\nexec "{sys.executable}" -m tlaup "$@"\n', encoding="utf-8")
    shim.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{shim.parent}{os.pathsep}{os.environ['PATH']}",
        "TLAUP_COMPLETION_SCRIPT": completion_script("bash"),
    }
    program = (
        'eval "$TLAUP_COMPLETION_SCRIPT"\n'
        'COMP_WORDS=(tlaup tool pin "")\n'
        "COMP_CWORD=3\n"
        "_tlaup_completion tlaup\n"
        'printf "%s\\n" "${COMPREPLY[@]}"\n'
    )
    done = subprocess.run(
        [bash, "--norc", "--noprofile", "-c", program],
        capture_output=True,
        text=True,
        env=env,
        timeout=SHELL_SECONDS,
        check=False,
    )
    assert done.returncode == 0, done.stderr
    assert done.stderr == ""
    words = done.stdout.splitlines()
    assert format_build(live_build) in words, words
    assert live_build.name in words, words


@pytest.mark.parametrize(("shell", "check"), [("zsh", ("-f", "-n")), ("fish", ("--no-config", "--no-execute"))])
def test_zsh_fish_syntax(shell: str, check: tuple[str, ...], tmp_path: Path) -> None:
    """``zsh -n`` and ``fish --no-execute`` accept the scripts tlaup prints, each where its shell is installed."""
    program = shutil.which(shell)
    if program is None:
        pytest.skip(f"{shell} is not on PATH")
    script = tmp_path / f"tlaup.{shell}"
    script.write_text(completion_script(shell), encoding="utf-8")
    done = subprocess.run(
        [program, *check, str(script)], capture_output=True, text=True, timeout=SHELL_SECONDS, check=False
    )
    assert done.returncode == 0, done.stderr
