"""`ENTRY_POINTS` against the class lists of two jars (design 21 S4): the main classes exist where they should."""

from __future__ import annotations

from pathlib import Path

import pytest

from tlaup.tools import ENTRY_POINTS

DATA = Path(__file__).parent.parent / "data" / "jar-classes"


def classes(name: str) -> set[str]:
    lines = (DATA / f"{name}.txt").read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith("# "), "the first line names the build the list was read from"
    return set(lines[1:])


def class_file(main_class: str) -> str:
    return main_class.replace(".", "/") + ".class"


def test_the_table_names_the_four_main_classes() -> None:
    assert dict(ENTRY_POINTS) == {
        "tlc": "tlc2.TLC",
        "sany": "tla2sany.SANY",
        "pcal": "pcal.trans",
        "repl": "tlc2.REPL",
    }


@pytest.mark.parametrize("tool", sorted(ENTRY_POINTS))
def test_every_entry_point_is_a_class_of_the_rolling_jar(tool: str) -> None:
    assert class_file(ENTRY_POINTS[tool]) in classes("rolling")


def test_the_repl_is_not_in_v1_7_4_and_the_other_three_are() -> None:
    old = classes("v1.7.4")
    assert class_file(ENTRY_POINTS["repl"]) not in old
    for tool in ("tlc", "sany", "pcal"):
        assert class_file(ENTRY_POINTS[tool]) in old


def test_the_class_lists_are_sorted_and_hold_class_names_only() -> None:
    for name in ("rolling", "v1.7.4"):
        lines = (DATA / f"{name}.txt").read_text(encoding="utf-8").splitlines()[1:]
        assert lines == sorted(lines)
        assert all(line.endswith(".class") for line in lines)
