"""`sany_exit_code` (design 21 S1 step 6, decisions D29 and D55) on hand-built outcomes and results."""

from __future__ import annotations

import pytest

from tlaup.java.launcher import ProcessOutcome
from tlaup.tools.sany import sany_exit_code
from tlaup_parse import Diagnostic, SanyResult


def diagnostic(severity: str) -> Diagnostic:
    return Diagnostic("sany", severity, "message", None, None, None)


def result(*severities: str) -> SanyResult:
    return SanyResult(tuple(diagnostic(s) for s in severities), {}, (), 0)


def process(
    code: int = 0, *, stopped_by: str | None = None, closed_pipe: bool = False, tool: int | None = 0
) -> ProcessOutcome:
    return ProcessOutcome(code, tool, stopped_by, (), closed_pipe)  # type: ignore[arg-type]


def test_an_error_gives_150_whatever_sany_returned() -> None:
    assert sany_exit_code(process(0), result("error")) == 150
    assert sany_exit_code(process(255, tool=255), result("error")) == 150
    assert sany_exit_code(process(0), result("warning", "error")) == 150


def test_a_warning_alone_changes_nothing() -> None:
    assert sany_exit_code(process(0), result("warning")) == 0
    assert sany_exit_code(process(255, tool=255), result("warning")) == 255


def test_sanys_own_code_stands_when_there_is_no_diagnostic() -> None:
    assert sany_exit_code(process(255, tool=255), result()) == 255
    assert sany_exit_code(process(0), result()) == 0


@pytest.mark.parametrize(("name", "code"), [("int", 130), ("term", 143), ("hup", 129)])
@pytest.mark.parametrize("severities", [(), ("error",), ("warning",)])
def test_a_signal_gives_its_code_whatever_the_diagnostics(name: str, code: int, severities: tuple[str, ...]) -> None:
    assert sany_exit_code(process(code, stopped_by=name), result(*severities)) == code


@pytest.mark.parametrize("severities", [(), ("error",)])
def test_a_closed_pipe_gives_141_whatever_the_diagnostics(severities: tuple[str, ...]) -> None:
    assert sany_exit_code(process(141, closed_pipe=True), result(*severities)) == 141
