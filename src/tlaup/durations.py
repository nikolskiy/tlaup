"""The one way tlaup writes a duration (design 22 O2): the result line and the "Checkpoint kept" note (11 R6)."""

from __future__ import annotations

import math

TEN_SECONDS = 10
MINUTE = 60
HOUR = 3600


def _half_up(value: float) -> int:
    return math.floor(value + 0.5)


def format_elapsed(seconds: float) -> str:
    """``0.7 s`` and ``4.2 s`` below ten seconds, ``45 s`` below a minute, ``2 min 13 s`` below an hour, then
    ``2 h 13 min``. A value is rounded first and then given the form of what it rounded to, so 9.96 seconds is
    ``10 s`` and 59.6 seconds ``1 min 00 s``."""
    seconds = max(seconds, 0.0)
    tenths = _half_up(seconds * 10)
    if tenths < TEN_SECONDS * 10:
        return f"{tenths / 10:.1f} s"
    whole = _half_up(seconds)
    if whole < MINUTE:
        return f"{whole} s"
    if whole < HOUR:
        return f"{whole // MINUTE} min {whole % MINUTE:02d} s"
    minutes = _half_up(whole / MINUTE)
    return f"{minutes // 60} h {minutes % 60:02d} min"
