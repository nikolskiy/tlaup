"""Reporters: the classes that show a run, behind one protocol (`base`).

`make_reporter` is the one function in which a command chooses a reporter (22 O1). Keep this module free of
module-level imports beyond the standard library's, so that importing the command layer does not load `rich` or
the reporter modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.reporters.base import Reporter

# Rich draws nothing live under these (tried on the locked Rich 13.9.4: no enter sequence and no frame for either).
_DUMB_TERMS = frozenset({"dumb", "unknown"})


@dataclass(frozen=True)
class ReporterOptions:
    """What the command's options say about the output; a value left unset comes from the settings."""

    plain: bool = False  # --plain given
    refresh_interval: float | None = None  # --refresh-interval given


def wants_layout(ctx: AppContext, options: ReporterOptions) -> bool:
    """22 O4, "When it is on", apart from the size, which the reporter reads at `start`: both streams are
    terminals, ``TERM`` is not ``dumb``, and plain output was not asked for by the flag or by ``tlc.plain``."""
    ui = ctx.ui
    if not (ui.out.is_terminal and ui.err.is_terminal):
        return False
    if ctx.env.get("TERM", "").strip().lower() in _DUMB_TERMS:
        return False
    return not (options.plain or ctx.settings.tlc.plain)


def make_reporter(ctx: AppContext, options: ReporterOptions) -> Reporter:
    """The `TerminalReporter` on ``ctx.ui`` with the real clock, in layout mode when `wants_layout` says so and in
    plain mode otherwise; milestone 4's ``--json`` attaches here."""
    import time  # noqa: PLC0415 - nothing loaded at import (14 F9)

    from tlaup.reporters.terminal import TerminalReporter  # noqa: PLC0415

    interval = options.refresh_interval
    if interval is None:
        interval = ctx.settings.tlc.refresh_interval
    if wants_layout(ctx, options):
        return TerminalReporter(ctx.ui, mode="layout", interval=interval, clock=time.monotonic)
    return TerminalReporter(ctx.ui, mode="plain", interval=interval, clock=time.monotonic)
