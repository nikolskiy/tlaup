"""The main class of each tool the jar runs (design 21 S4): the one place a main class is named."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

ENTRY_POINTS: Mapping[str, str] = {
    "tlc": "tlc2.TLC",
    "sany": "tla2sany.SANY",
    "pcal": "pcal.trans",
    "repl": "tlc2.REPL",
}
