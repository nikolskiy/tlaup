"""The When steps of design 01 T5 that package 18 owns; each wraps a runner.

In-process unless one of T5's five situations applies (T12 rule 10); the in-process step refuses two
of them itself.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import parsers, when

if TYPE_CHECKING:
    from tests.steps._scenario import Scenario


@when(parsers.re(r'I run "(?P<command>[^"]+)"'))
def i_run(scenario: Scenario, command: str) -> None:
    scenario.run_in_process(command)
