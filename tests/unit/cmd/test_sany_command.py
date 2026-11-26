"""`tlaup sany` where a feature scenario cannot reach: the summary's wording, and what the sink does to a tab."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from tlaup.cmd.sany import PrintingSink, summary
from tlaup.java.launcher import ProcessOutcome
from tlaup.tools.sany import SanyOutcome
from tlaup.ui import Ui
from tlaup_parse import Diagnostic, Location, SanyResult

if TYPE_CHECKING:
    from pathlib import Path


def diagnostic(severity: str, *, file: str | None = None, location: Location | None = None) -> Diagnostic:
    return Diagnostic("sany", severity, "message", None, file, location)


def outcome(*severities: str) -> SanyOutcome:
    result = SanyResult(tuple(diagnostic(s) for s in severities), {}, (), 0)
    return SanyOutcome(result, ProcessOutcome(0, 0, None, ()), 0)


@pytest.mark.parametrize(
    ("severities", "text"),
    [
        ((), "no errors"),
        (("error",), "1 error, 0 warnings"),
        (("error", "error", "warning"), "2 errors, 1 warning"),
        (("warning",), "0 errors, 1 warning"),
        (("warning", "warning"), "0 errors, 2 warnings"),
    ],
)
def test_the_summary_pluralises_as_english_does(severities: tuple[str, ...], text: str) -> None:
    assert summary(outcome(*severities)) == text


def test_a_tab_stays_a_tab_and_markup_is_text(tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    ui = Ui(out, err, io.StringIO(), color=False, env={"COLUMNS": "40"})
    spec = tmp_path / "Tab.tla"
    spec.write_text("---- MODULE Tab ----\n\tx == [bold]y\n====\n", encoding="utf-8")
    sink = PrintingSink(ui, cwd=tmp_path, spec=spec)
    sink.diagnostic(diagnostic("error", file=str(spec), location=Location("Tab", 2, 8, 2, 8)))
    sink.chatter("Parsing file [red]x[/red]\twith a tab")
    assert "\tx == [bold]y" in out.getvalue()
    assert "Tab.tla:2:8: error: message" in out.getvalue()
    assert err.getvalue() == "Parsing file [red]x[/red]\twith a tab\n"
    sink.other("x" * 100)
    assert "x" * 100 + "\n" in out.getvalue()  # never wrapped at 40 columns
