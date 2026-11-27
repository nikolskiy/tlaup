"""``describe_exit_status`` against design 02 X1's table "The meaning of a code", copied here once (10 P2)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tlaup_parse import ExitStatus, describe_exit_status

# (code, word, meaning), word for word from 02 X1.
TABLE = [
    (0, "success", "TLC checked the spec and found nothing wrong."),
    (
        1,
        "usage error",
        "TLC rejected its command line, or the JVM could not start it for an option it does not accept or a main "
        "class it cannot find.",
    ),
    (10, "assumption failure", "An assumption in the spec is false."),
    (11, "deadlock failure", "A reachable state has no successor."),
    (12, "safety failure", "An invariant was violated."),
    (13, "liveness failure", "A temporal property or an action property was violated."),
    (14, "assertion failure", "An `Assert` in the spec failed."),
    (75, "evaluation failure", "TLC could not evaluate part of the spec, or Java ran out of memory."),
    (76, "evaluation failure", "Evaluating an invariant failed."),
    (77, "evaluation failure", "Evaluating a liveness property failed."),
    (150, "parse error", "The spec does not parse, or fails SANY's semantic checks."),
    (151, "configuration error", "The cfg file is missing or wrong."),
    (152, "state space too large", "The state space is too large for TLC to check."),
    (153, "system error", "TLC stopped on a system error."),
    (255, "error", "TLC stopped on an error it does not classify; its output above says what went wrong."),
]
UNKNOWN_MEANING = "TLC ended with a code tlaup does not know."
KNOWN_CODES = {code for code, _, _ in TABLE}


@pytest.mark.parametrize(("code", "word", "meaning"), TABLE, ids=[str(row[0]) for row in TABLE])
def test_each_row_of_the_table(code: int, word: str, meaning: str) -> None:
    assert describe_exit_status(code) == ExitStatus(code=code, word=word, meaning=meaning, known=True)


@pytest.mark.parametrize("code", [3, 99, 128, -1])
def test_a_code_the_table_does_not_hold(code: int) -> None:
    assert describe_exit_status(code) == ExitStatus(code=code, word="error", meaning=UNKNOWN_MEANING, known=False)


@pytest.mark.parametrize(
    ("code", "name"),
    [(130, "SIGINT"), (137, "SIGKILL"), (143, "SIGTERM"), (139, "SIGSEGV")],
)
def test_a_code_above_128_the_table_does_not_hold_is_a_signal(code: int, name: str) -> None:
    assert describe_exit_status(code) == ExitStatus(
        code=code, word="error", meaning=f"Java was stopped by a signal ({name}).", known=False
    )


@pytest.mark.parametrize("code", [200, 1000])
def test_a_code_above_128_that_is_no_known_signal_gives_its_number(code: int) -> None:
    status = describe_exit_status(code)
    assert (status.word, status.known) == ("error", False)
    assert status.meaning == f"Java was stopped by a signal ({code - 128})."


@given(st.integers())
def test_never_raises_and_returns_the_code(code: int) -> None:
    status = describe_exit_status(code)
    assert status.code == code
    assert status.known == (code in KNOWN_CODES)
