"""``format_elapsed``, the one duration form (design 22 O2, 11 R6; package 35)."""

from __future__ import annotations

import pytest

from tlaup.durations import format_elapsed


@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (0.7, "0.7 s"),
        (4.2, "4.2 s"),
        (45, "45 s"),
        (60, "1 min 00 s"),
        (133, "2 min 13 s"),
        (3720, "1 h 02 min"),
        (7980, "2 h 13 min"),
    ],
)
def test_each_form(seconds: float, text: str) -> None:
    assert format_elapsed(seconds) == text


@pytest.mark.parametrize(("seconds", "text"), [(9.96, "10 s"), (59.6, "1 min 00 s"), (3599.6, "1 h 00 min")])
def test_a_value_that_rounds_into_the_next_form_takes_it(seconds: float, text: str) -> None:
    assert format_elapsed(seconds) == text


def test_zero_and_below() -> None:
    assert format_elapsed(0) == "0.0 s"
    assert format_elapsed(-1) == "0.0 s"
