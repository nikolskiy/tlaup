"""`make_reporter`'s rule between the layout and plain output (design 22 O4, "When it is on"; 02 X2; package 40a).

The context is built in the test, with a `Ui` on `StringIO` streams forced to terminal mode or not; the mode is
read from what the reporter writes when it starts: the layout writes the enter sequence of the alternate screen,
plain mode only the header. The size is the reporter's own check (``test_layout.py``).
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from tests.unit.reporters.replay import load_case, make_run
from tlaup.context import AppContext
from tlaup.paths import AppPaths
from tlaup.reporters import ReporterOptions, make_reporter
from tlaup.reporters.terminal import TerminalReporter
from tlaup.ui import Ui

if TYPE_CHECKING:
    from pathlib import Path

ENTER = "\x1b[?1049h"


@pytest.fixture(autouse=True)
def terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rich reads ``TERM`` from the process to draw (O6); the rule reads it from the context's environment."""
    monkeypatch.setenv("TERM", "xterm-256color")


def make_context(
    home: Path, *, out_terminal: bool = True, err_terminal: bool = True, **env: str
) -> tuple[AppContext, io.StringIO]:
    environment = {"TLAUP_HOME": str(home), "TERM": "xterm-256color", **env}
    err = io.StringIO()
    ui = Ui(io.StringIO(), err, io.StringIO(), color=False, env=environment, terminal=True, size=(100, 30))
    if not out_terminal:
        ui.out = Ui(io.StringIO(), err, io.StringIO(), color=False, env=environment, terminal=False).out
    if not err_terminal:
        ui.err = Ui(io.StringIO(), err, io.StringIO(), color=False, env=environment, terminal=False).err
    context = AppContext(paths=AppPaths.from_env(environment), env=environment, debug=False, ui=ui)
    return context, err


def draws_layout(context: AppContext, err: io.StringIO, options: ReporterOptions | None = None) -> bool:
    reporter = make_reporter(context, options or ReporterOptions())
    reporter.start(make_run(load_case("v1.7.4", "violation")))
    reporter.close()
    return ENTER in err.getvalue()


def test_both_streams_on_a_terminal_give_the_layout(tmp_path: Path) -> None:
    assert draws_layout(*make_context(tmp_path))


@pytest.mark.parametrize(
    ("changes", "options"),
    [
        pytest.param({}, ReporterOptions(plain=True), id="--plain"),
        pytest.param({"TLAUP_TLC_PLAIN": "1"}, None, id="TLAUP_TLC_PLAIN=1"),
        pytest.param({"out_terminal": False}, None, id="stdout not a terminal"),
        pytest.param({"err_terminal": False}, None, id="stderr not a terminal"),
        pytest.param({"TERM": "dumb"}, None, id="TERM=dumb"),
        pytest.param({"TERM": "unknown"}, None, id="TERM=unknown"),
    ],
)
def test_each_of_these_gives_plain_output(
    tmp_path: Path, changes: dict[str, object], options: ReporterOptions | None
) -> None:
    context, err = make_context(tmp_path, **changes)  # type: ignore[arg-type]
    assert not draws_layout(context, err, options)
    assert err.getvalue().startswith("TLC v1.7.4@5a47802")


def test_tlc_plain_in_the_settings_file_gives_plain_output(tmp_path: Path) -> None:
    context, err = make_context(tmp_path)
    context.paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    context.paths.config_file.write_text("tlc:\n  plain: true\n", encoding="utf-8")
    assert not draws_layout(context, err)


def test_tlaup_tlc_plain_false_undoes_the_setting_for_one_run(tmp_path: Path) -> None:
    context, err = make_context(tmp_path, TLAUP_TLC_PLAIN="false")
    context.paths.config_file.parent.mkdir(parents=True, exist_ok=True)
    context.paths.config_file.write_text("tlc:\n  plain: true\n", encoding="utf-8")
    assert draws_layout(context, err)


def _rate(context: AppContext, options: ReporterOptions) -> float:
    reporter = make_reporter(context, options)
    assert isinstance(reporter, TerminalReporter)
    reporter.start(make_run(load_case("v1.7.4", "violation")))
    try:
        assert reporter.live is not None
        return reporter.live.refresh_per_second
    finally:
        reporter.close()


def test_the_interval_is_the_settings_by_default(tmp_path: Path) -> None:
    context, _ = make_context(tmp_path)
    assert _rate(context, ReporterOptions()) == 1  # tlc.refresh_interval, 1.0 (R13's in-process half)


def test_the_interval_comes_from_the_setting_and_the_option_wins(tmp_path: Path) -> None:
    context, _ = make_context(tmp_path, TLAUP_TLC_REFRESH_INTERVAL="0.25")
    assert _rate(context, ReporterOptions()) == 4
    assert _rate(context, ReporterOptions(refresh_interval=0.5)) == 2
