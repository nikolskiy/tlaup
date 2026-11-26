"""What a TLC exit code means: design 02 X1's table "The meaning of a code" as data (10 P2, decision D63).

The words become the JSON of milestone 4, so they are copied from X1 and never reworded. A "failure" is TLC
having checked the spec and found something wrong; an "error" is TLC not having been able to check it.
"""

from __future__ import annotations

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
    10: ("assumption failure", "An assumption of the spec is false; on rolling also a postcondition."),
    11: ("deadlock failure", "A reachable state has no successor."),
    12: ("safety failure", "An invariant was violated."),
    13: ("liveness failure", "A temporal property or an action property was violated."),
    14: ("assertion failure", "An `Assert` in the spec failed."),
    75: (
        "evaluation failure",
        "Evaluating the spec failed, for example while computing the initial states, or Java ran out of memory.",
    ),
    76: ("evaluation failure", "Evaluating an invariant failed."),
    77: ("evaluation failure", "Evaluating a liveness property failed."),
    150: ("parse error", "The spec does not parse, or fails SANY's semantic checks."),
    151: ("configuration error", "The cfg file is wrong, or on rolling missing."),
    152: ("state space too large", "Upstream's name for a code TLC declares; no supported build returns it."),
    153: ("system error", "Upstream's name for a code TLC declares; no supported build returns it."),
    255: ("error", "TLC stopped on an error it does not classify, for example a missing cfg on v1.7.4."),
}
# X1's last row, "any other": nobody can say of an undocumented code that something was checked and found wrong.
_UNKNOWN = ("error", "TLC returned a code it does not document.")


def describe_exit_status(code: int) -> ExitStatus:
    """The word and meaning X1 gives TLC's exit code ``code``; never raises."""
    row = _TABLE.get(code)
    if row is None:
        return ExitStatus(code=code, word=_UNKNOWN[0], meaning=_UNKNOWN[1], known=False)
    return ExitStatus(code=code, word=row[0], meaning=row[1], known=True)
