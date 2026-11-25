"""Every fact of ``facts.py`` on every TLC build folder whose line it holds for (design 01 T3, 10 P1; package 08).

``test_fact`` is the one test per fact and build; it is marked ``pending`` while the parser does not exist, by
the patterns of ``PENDING``, and the parser packages narrow them (13a to ``("*:traces:*",)``, 13b to ``()``).
The other four tests check the facts themselves and pass now.
"""

from __future__ import annotations

import fnmatch
import re
from collections import Counter
from typing import TYPE_CHECKING

import pytest

from tests.parse.drive import build_folders, cases_of, line_of, parse_tlc
from tests.parse.facts import FACTS, LINES, facts_for

if TYPE_CHECKING:
    from pathlib import Path

    from tests.parse.facts import Fact

PENDING: tuple[str, ...] = ("*",)  # fnmatch patterns over Fact.id; a fact whose id matches one is marked pending

# 08a writes the facts of the cases from research 1, 2, 13 and 28; 08b adds research 22's and removes this.
COVERED_SOURCES = frozenset({1, 2, 13, 28})
_SOURCE = re.compile(r"^research (\d+),")


def _is_pending(fact: Fact) -> bool:
    return any(fnmatch.fnmatchcase(fact.id, pattern) for pattern in PENDING)


def _fact_params() -> list[object]:
    params: list[object] = []
    for folder in build_folders("tlc"):
        line = line_of(folder)
        for case in cases_of(folder):
            for fact in facts_for(case, line):
                marks = [pytest.mark.pending] if _is_pending(fact) else []
                params.append(pytest.param(folder, fact, id=f"{folder.name}/{fact.id}", marks=marks))
    return params


@pytest.mark.parametrize(("folder", "fact"), _fact_params())
def test_fact(folder: Path, fact: Fact) -> None:
    fact.check(parse_tlc(folder / f"{fact.case}.out"))


def _covered(table: dict[str, object]) -> bool:
    match = _SOURCE.match(str(table.get("source", "")))
    return match is not None and int(match.group(1)) in COVERED_SOURCES


def test_every_covered_case_has_facts_for_its_line() -> None:
    missing = [
        f"{folder.name}/{case}"
        for folder in build_folders("tlc")
        for case, table in cases_of(folder).items()
        if _covered(table) and not facts_for(case, line_of(folder))
    ]
    assert missing == []


def test_every_fact_names_a_case_of_every_line_it_holds_for() -> None:
    cases_by_line: dict[str, set[str]] = {line: set() for line in LINES}
    for folder in build_folders("tlc"):
        cases_by_line[line_of(folder)].update(cases_of(folder))
    wrong = [
        (fact.id, sorted(fact.lines))
        for fact in FACTS
        if not fact.lines or not fact.lines <= LINES or any(fact.case not in cases_by_line[line] for line in fact.lines)
    ]
    assert wrong == []


def test_fact_ids_are_unique() -> None:
    counts = Counter(fact.id for fact in FACTS)
    assert sorted(i for i, n in counts.items() if n > 1) == []


def test_every_pending_pattern_matches_a_fact() -> None:
    stale = [pattern for pattern in PENDING if not any(fnmatch.fnmatchcase(fact.id, pattern) for fact in FACTS)]
    assert stale == []
