"""What the commands that run a tool share: the ``get_build`` wrapper round ``ensure_tools`` (design 20 G1, 12 V9).

Moved here from ``cmd/tlc.py`` by package 41, so that ``tlc``, ``sany``, ``pcal`` and ``repl`` use one. Nothing heavy
is imported at the top (design 14 F9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    from tlaup.context import AppContext
    from tlaup.versioning.store import Build


SPEC_HELP = "A TLA+ spec: a name (`Spec`), a file (`Spec.tla`) or a path. `spec/Spec.tla` is tried too."


def run_build(app: AppContext, auto_install: str | None) -> Callable[[], Build]:
    """``get_build`` for a run: the pin, or the first-run question or install (12 V9). The GitHub client, and so
    ``requests``, is built only when nothing is installed and ``ensure_tools`` may install or ask (14 F9)."""

    def get_build() -> Build:
        from tlaup.cmd.tool._shared import download_progress, open_remote, open_store, pinned_build
        from tlaup.versioning.first_run import ensure_tools

        store = open_store(app)
        if store.pinned() is not None or store.builds():
            return pinned_build(store)  # the pin, or NoPinnedBuild naming the builds to pin
        client, remote = open_remote(app)
        with download_progress(app.ui) as progress:
            return ensure_tools(store, remote, client, app.ui, auto_install=auto_install, progress=progress)

    return get_build
