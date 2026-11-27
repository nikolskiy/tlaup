"""What a TLC exit code means: design 02 X1's table "The meaning of a code" as data (10 P2, decision D63).

The words become the JSON of milestone 4, so they are copied from X1 and never reworded. The meaning sentences
are for people, are copied from X1's current table, and may be reworded there (they were, on 2026-11-27, to read
as plain statements); the two sentences for a code the table does not hold are made here, as X1's last row says.
A "failure" is TLC having checked the spec and found something wrong; an "error" is TLC not having been able to
check it.
"""

from __future__ import annotations

import signal
from dataclasses import dataclass


@dataclass(frozen=True)
class ExitStatus:
    code: int
    word: str  # X1's word for the code: "success", "safety failure", "parse error", ... (D63);
    # the JSON of milestone 4 carries it
    meaning: str  # X1's sentence for the code; the result line of 22 O3 shows it beside the verdict
    known: bool  # False for a code X1's table does not hold


# code -> (word, meaning), one entry per row of X1's table.
_TABLE: dict[int, tuple[str, str]] = {
    0: ("success", "TLC checked the spec and found nothing wrong."),
    1: (
        "usage error",
        "TLC rejected its command line, or the JVM could not start it for an option it does not accept or a main "
        "class it cannot find.",
    ),
    10: ("assumption failure", "An assumption in the spec is false."),
    11: ("deadlock failure", "A reachable state has no successor."),
    12: ("safety failure", "An invariant was violated."),
    13: ("liveness failure", "A temporal property or an action property was violated."),
    14: ("assertion failure", "An `Assert` in the spec failed."),
    75: ("evaluation failure", "TLC could not evaluate part of the spec, or Java ran out of memory."),
    76: ("evaluation failure", "Evaluating an invariant failed."),
    77: ("evaluation failure", "Evaluating a liveness property failed."),
    150: ("parse error", "The spec does not parse, or fails SANY's semantic checks."),
    151: ("configuration error", "The cfg file is missing or wrong."),
    152: ("state space too large", "The state space is too large for TLC to check."),
    153: ("system error", "TLC stopped on a system error."),
    255: ("error", "TLC stopped on an error it does not classify; its output above says what went wrong."),
}
# X1's last two rows: nobody can say of an undocumented code that something was checked and found wrong.
_UNKNOWN_WORD = "error"
_UNKNOWN_MEANING = "TLC ended with a code tlaup does not know."
_MAX_CODE = 255  # a larger code (a Windows crash code such as 3221225477) is no signal
_SIGNAL_BASE = 128  # a shell reports a process killed by signal N as 128 + N; so does Java's launcher


def _signal_meaning(number: int) -> str:
    try:
        name = signal.Signals(number).name
    except ValueError:
        name = str(number)
    return f"Java was stopped by a signal ({name})."


def describe_exit_status(code: int) -> ExitStatus:
    """The word and meaning X1 gives TLC's exit code ``code``; never raises.

    A code from 129 to 255 that the table does not hold means Java was stopped by signal ``code - 128``; the name comes
    from the platform's ``signal.Signals`` (numbers differ between systems, such as 7 and 10 for SIGBUS).
    """
    row = _TABLE.get(code)
    if row is not None:
        return ExitStatus(code=code, word=row[0], meaning=row[1], known=True)
    meaning = _signal_meaning(code - _SIGNAL_BASE) if _SIGNAL_BASE < code <= _MAX_CODE else _UNKNOWN_MEANING
    return ExitStatus(code=code, word=_UNKNOWN_WORD, meaning=meaning, known=False)
