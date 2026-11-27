"""The steps package 39 adds outside T5's table: the signals the fake java received and its process group.

The fake's log already holds both (design 01 T4): a ``signal`` line for each signal it handled, and the process
group id in each ``start`` line. ``Outcome.pgid`` is tlaup's own group (package 18). The reason for each step is
in package 39's "Steps".
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from tests.steps._process import SIGNAL_NAMES
from tests.steps._scenario import fail

if TYPE_CHECKING:
    from tests.steps._scenario import Scenario

THEN = ", then "  # between two signals in "java received SIGINT, then SIGTERM"


def _posix() -> None:
    if os.name == "nt":
        pytest.skip("signals and process groups as POSIX has them; no Windows CI (D15)")


def received(scenario: Scenario) -> list[str]:
    """The names of the signals the fake java logged, in order, over the scenario's whole log (T5)."""
    return [str(line.get("name")) for line in scenario.fakes.log("java") if line.get("event") == "signal"]


def check_received(scenario: Scenario, names: str) -> None:
    """The fake logged exactly these signals, in this order, and no other."""
    _posix()
    wanted = names.split(THEN)
    unknown = [name for name in wanted if name not in SIGNAL_NAMES]
    if unknown:
        fail(f"the fake java logs {', '.join(SIGNAL_NAMES)}, not {', '.join(unknown)}")
    actual = received(scenario)
    if actual != wanted:
        fail(f"java received {actual or 'no signal'}, not {wanted}")


def check_no_signal(scenario: Scenario) -> None:
    _posix()
    actual = received(scenario)
    if actual:
        fail(f"java received {actual}, not no signal")


def check_group(scenario: Scenario, *, own: bool) -> None:
    """The last tool start's process group against tlaup's: different (D60, a parsed run) or the same (raw)."""
    _posix()
    tlaup_group = scenario.result().pgid
    if tlaup_group is None:
        fail('tlaup\'s process group is known for a real process only: "as a process", "I start" or "in a terminal"')
    start = scenario.last_tool_start()
    group = start.get("pgid")
    if own and group == tlaup_group:
        fail(f"java ran in tlaup's process group {tlaup_group}, not in one of its own")
    if not own and group != tlaup_group:
        fail(f"java ran in the process group {group}, not in tlaup's {tlaup_group}")
