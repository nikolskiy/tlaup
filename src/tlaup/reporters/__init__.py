"""Reporters: the classes that show a run, behind one protocol (`base`).

`make_reporter` is the one function in which a command chooses a reporter (22 O1). Keep this module free of
module-level imports, so that importing the command layer does not load `rich` or the reporter modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.reporters.base import Reporter


def make_reporter(ctx: AppContext) -> Reporter:
    """The plain `TerminalReporter` on ``ctx.ui``, with the real clock. Package 40 adds the options and the rule
    between plain and live output; milestone 4's ``--json`` attaches here."""
    import time  # noqa: PLC0415 - nothing loaded at import (14 F9)

    from tlaup.reporters.terminal import TerminalReporter  # noqa: PLC0415

    return TerminalReporter(ctx.ui, clock=time.monotonic)
