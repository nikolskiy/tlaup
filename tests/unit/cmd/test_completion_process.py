"""The three shells' protocol with Typer, as real processes and no shell (design 23 C3; package 47).

These use the variables the generated scripts use. They fail first when a Typer release changes the protocol.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from tests.steps._process import start
from tests.unit.cmd.test_completion import prepare_store
from tlaup.cmd.completion import complete_installed

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import Isolated

pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX process start (D15: no Windows CI)")
TIMEOUT = 60  # seconds; a wait's limit, not a measurement


def complete(extra: dict[str, str]) -> tuple[int, str]:
    process = start(
        [sys.executable, "-m", "tlaup"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, **extra},
    )
    out, _ = process.communicate(timeout=TIMEOUT)
    return process.returncode, out.decode()


def test_bash_gives_the_installed_words_one_per_line(isolated: Isolated, tmp_path: Path) -> None:
    prepare_store(isolated, tmp_path)
    code, out = complete({"_TLAUP_COMPLETE": "complete_bash", "COMP_WORDS": "tlaup tool pin ", "COMP_CWORD": "3"})
    assert code == 0
    assert out.splitlines() == complete_installed("")


def test_bash_gives_nothing_after_the_at_sign_it_split_the_word_at(isolated: Isolated, tmp_path: Path) -> None:
    prepare_store(isolated, tmp_path)
    extra = {"_TLAUP_COMPLETE": "complete_bash", "COMP_WORDS": "tlaup tool pin rolling @ ", "COMP_CWORD": "5"}
    code, out = complete(extra)
    assert code == 0
    assert out.strip() == ""  # no word; Typer ends the empty list with a line break


def test_fish_gives_each_installed_word(isolated: Isolated, tmp_path: Path) -> None:
    prepare_store(isolated, tmp_path)
    code, out = complete(
        {
            "_TLAUP_COMPLETE": "complete_fish",
            "_TYPER_COMPLETE_ARGS": "tlaup tool pin ",
            "_TYPER_COMPLETE_FISH_ACTION": "get-args",
        }
    )
    assert code == 0
    assert out.splitlines() == complete_installed("")


def test_zsh_gives_an_arguments_call_that_names_each_installed_word(isolated: Isolated, tmp_path: Path) -> None:
    prepare_store(isolated, tmp_path)
    code, out = complete({"_TLAUP_COMPLETE": "complete_zsh", "_TYPER_COMPLETE_ARGS": "tlaup tool pin "})
    assert code == 0
    assert out.startswith("_arguments ")
    for word in complete_installed(""):
        assert f'"{word}"' in out


def test_a_malformed_config_file_does_not_disturb_completion(isolated: Isolated, tmp_path: Path) -> None:
    prepare_store(isolated, tmp_path)
    isolated.paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    isolated.paths.config_file.write_text("tlc: [unclosed\n  : : :\n", encoding="utf-8")
    process = start(
        [sys.executable, "-m", "tlaup"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={**os.environ, "_TLAUP_COMPLETE": "complete_bash", "COMP_WORDS": "tlaup tool pin ", "COMP_CWORD": "3"},
    )
    out, err = process.communicate(timeout=TIMEOUT)
    assert process.returncode == 0
    assert err == b""
    assert out.decode().splitlines() == complete_installed("")
