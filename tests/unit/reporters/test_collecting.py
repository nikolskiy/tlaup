"""CollectingReporter, driven directly with hand-built events (01 T12, rule 1)."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from tlaup.reporters.base import Reporter, RunInfo
from tlaup.reporters.collecting import CollectingReporter
from tlaup_parse import OutputLine, PhaseChanged, RunResult, TlcMessage
from tlaup_parse.model import Phase

_typecheck: Reporter = CollectingReporter()


def make_run() -> RunInfo:
    anything: Any = object()
    return RunInfo(
        tool="tlc",
        spec=Path("Spec.tla"),
        cfg=None,
        build=anything,
        java=anything,
        workers=None,
        project_root=None,
        override_classes=(),
        command=("java", "-jar", "x.jar"),
        cwd=Path("work"),
    )


def test_keeps_everything_it_is_given() -> None:
    reporter = CollectingReporter()
    run, result = make_run(), RunResult()
    first = OutputLine("line 1")
    second = PhaseChanged(TlcMessage(code=1, severity=0, name=None, body=("one plain line",)), Phase.NOT_STARTED)
    outcome = object()

    reporter.start(run)
    reporter.handle(first, result)
    reporter.handle(second, result)
    reporter.stderr_line("err")
    reporter.notice("waiting")
    reporter.finish(outcome)
    reporter.close()
    reporter.close()

    assert reporter.run is run
    assert reporter.events == [first, second]
    assert reporter.results == [result, result]
    assert reporter.results[0] is result
    assert reporter.stderr_lines == ["err"]
    assert reporter.notices == ["waiting"]
    assert reporter.outcome is outcome
    assert reporter.calls == ["start", "handle", "handle", "stderr_line", "notice", "finish", "close"]
    assert reporter.write_error is None


def test_close_before_start() -> None:
    reporter = CollectingReporter()
    reporter.close()
    assert reporter.calls == ["close"]
    assert reporter.run is None
    assert reporter.events == []
    assert reporter.results == []
    assert reporter.stderr_lines == []
    assert reporter.notices == []
    assert reporter.outcome is None
    assert reporter.write_error is None


def test_calls_list_is_shared() -> None:
    calls: list[str] = ["note: before"]
    reporter = CollectingReporter(calls)
    reporter.start(make_run())
    assert reporter.calls is calls
    assert calls == ["note: before", "start"]


def test_run_info_is_frozen() -> None:
    run = make_run()
    with pytest.raises(dataclasses.FrozenInstanceError):
        run.tool = "sany"  # type: ignore[misc]
