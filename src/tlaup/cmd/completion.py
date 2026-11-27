"""`tlaup completion bash|zsh|fish`, the completers, and switching Typer's completion on (design 23 C3, 14 F9).

The one module under `src/` that imports Typer's private completion modules. Nothing heavy is imported at the
top (14 F9's one exception: this module is imported by `cli.py` and by the commands that name a completer): each
completer imports the store, the registry or the schema in its own body, inside the guard.

A completer runs on every Tab press: it makes no request, starts no Java, loads no settings and, for any reason
whatsoever, returns nothing instead of an error (C3).
"""

from __future__ import annotations

import functools
import os
from enum import StrEnum
from typing import TYPE_CHECKING, Annotated

import typer

if TYPE_CHECKING:
    from collections.abc import Callable

    from tlaup.versioning.store import ToolStore

COMPLETE_VAR = "_TLAUP_COMPLETE"
PROG_NAME = "tlaup"

HELP = (
    "Print the completion script of a shell.\n\n"
    "Put one line in the shell's start-up file: "
    'eval "$(tlaup completion bash)" in ~/.bashrc, '
    'eval "$(tlaup completion zsh)" in ~/.zshrc (after compinit), '
    "tlaup completion fish | source in ~/.config/fish/config.fish. "
    "Installed versions, module names and config keys are completed. "
    "In bash a build is completed up to its name; the part after @ is typed."
)
SHELL_HELP = "The shell: bash, zsh or fish."


class Shell(StrEnum):
    bash = "bash"
    zsh = "zsh"
    fish = "fish"


def completion(shell: Annotated[Shell, typer.Argument(metavar="SHELL", help=SHELL_HELP, show_default=False)]) -> None:
    from typer._completion_shared import get_completion_script

    from tlaup.ui import Ui

    # `shell` is the name of a shell to write a script for, not subprocess's shell=True.
    script = get_completion_script(prog_name=PROG_NAME, complete_var=COMPLETE_VAR, shell=shell.value)  # nosec B604
    Ui.for_process().result(script)


def init_completion() -> None:
    """Fill Typer's registry of shells; `main()` calls it only when ``_TLAUP_COMPLETE`` is set (C3)."""
    from typer._completion_classes import completion_init

    completion_init()


def _guarded(completer: Callable[[str], list[str]]) -> Callable[[str], list[str]]:
    """The one guard of every completer: whatever fails, the answer is no words (C3, 30 I8)."""

    @functools.wraps(completer)
    def guarded(incomplete: str) -> list[str]:
        try:
            return completer(incomplete)
        except Exception:  # noqa: BLE001 - the second blind except 30 I8 allows; C3: no error is printed
            return []

    return guarded


def _starting(words: list[str], incomplete: str) -> list[str]:
    """The words that start with ``incomplete``, in their order, each once."""
    return [word for word in dict.fromkeys(words) if word.startswith(incomplete)]


def _store() -> ToolStore:
    from datetime import UTC, datetime

    from tlaup.paths import AppPaths
    from tlaup.versioning.store import ToolStore

    return ToolStore(AppPaths.from_env(os.environ), now=lambda: datetime.now(UTC))


@_guarded
def complete_installed(incomplete: str) -> list[str]:
    """Every installed build in its printed form, each distinct name, `stable` and `rolling`."""
    from tlaup.versioning.spec import format_build

    builds = _store().builds()
    words = [format_build(build, builds) for build in builds]
    words += [build.name for build in builds]
    return _starting([*words, "stable", "rolling"], incomplete)


@_guarded
def complete_upgrade(incomplete: str) -> list[str]:
    """The distinct names of installed builds: `upgrade` takes a name and rejects `name@commit` (12 V4)."""
    return _starting([build.name for build in _store().builds()], incomplete)


@_guarded
def complete_install(incomplete: str) -> list[str]:
    """`stable`, `rolling` and the tags of the remembered release list; no request is made."""
    from tlaup.paths import AppPaths
    from tlaup.versioning.remote import cached_tags

    return _starting(["stable", "rolling", *cached_tags(AppPaths.from_env(os.environ).remote)], incomplete)


@_guarded
def complete_module(incomplete: str) -> list[str]:
    """The names of the registered modules."""
    from datetime import UTC, datetime

    from tlaup.modules.registry import Registry
    from tlaup.paths import AppPaths

    registry = Registry(AppPaths.from_env(os.environ).modules, now=lambda: datetime.now(UTC))
    return _starting([module.name for module in registry.list()], incomplete)


@_guarded
def complete_config_key(incomplete: str) -> list[str]:
    """The dotted keys of the schema."""
    from tlaup.config.schema import setting_keys

    return _starting(list(setting_keys()), incomplete)


@_guarded
def complete_spec(incomplete: str) -> list[str]:
    """The `*.tla` files and the folders that start with ``incomplete``, a relative path looked up in its folder.

    Typer's own copy of Click drops the file type of a `Path` argument when it prints the words, so a `Path`
    type asks no shell for files. With no word at all bash and zsh fall back to every file; fish does not (its
    script uses --no-files), so it completes nothing. These words work in all three shells.
    """
    from pathlib import Path

    head, _, tail = incomplete.rpartition("/")
    prefix = incomplete[: len(incomplete) - len(tail)]  # everything up to and with the last slash
    folder = Path(head) if head else Path("/" if incomplete.startswith("/") else ".")
    found = []
    for entry in sorted(folder.iterdir(), key=lambda e: e.name):
        if not entry.name.lower().startswith(tail.lower()) or (entry.name.startswith(".") and not tail):
            continue
        if entry.is_dir():
            found.append(f"{prefix}{entry.name}/")
        elif entry.suffix == ".tla":
            found.append(f"{prefix}{entry.name}")
    return found
