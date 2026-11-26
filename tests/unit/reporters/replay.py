"""Replays a golden TLC case through a real `TlcParser` into a `TerminalReporter` (design 22 O6, package 38).

The case is read as the runner reads it (``tests/parse/drive.py``: binary, lines keep their newline, decoded as the
launcher decodes). The folder SANY named in the capture's ``Parsing file`` lines is mapped to the case's folder
under ``golden/specs/``, so the reporter reads the spec for the source excerpt and the coverage view as in a real
run; ``map_folder=False`` leaves the lines as captured. Nothing in the output is normalised (01 T8): the fixed
`RunInfo` and the clock, one second per call, are what keep it stable. Package 40 reuses this helper for the
layout mode.
"""

from __future__ import annotations

import io
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from tests.parse.drive import cases_of, golden_root, read_lines
from tlaup.java.locate import JavaRuntime, JavaTool
from tlaup.reporters.base import RunInfo
from tlaup.reporters.terminal import TerminalReporter
from tlaup.tlc.runner import RunOutcome
from tlaup.ui import Ui
from tlaup.versioning.store import Build, Source
from tlaup_parse import RunResult, TlcParser

if TYPE_CHECKING:
    from collections.abc import Callable

    from tlaup_parse import Event

JAVA_VERSION = "25.0.5"
WIDTH = 100
HEIGHT = 30
_PARSING = "Parsing file "


def tlc_folder(build: str) -> Path:
    """``tests/parse/golden/tlc/<build>``."""
    return golden_root() / "tlc" / build


def specs_root() -> Path:
    return golden_root() / "specs"


class SecondClock:
    """A clock that advances one second per call (O6)."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return float(self.calls)


class EventClock:
    """A clock that advances one second per event the replay hands over, whoever reads it (O6, layout mode): the
    frames a test draws do not move it."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def tick(self) -> None:
        self.now += 1.0


def make_ui(
    *,
    width: int = WIDTH,
    height: int = HEIGHT,
    color: bool = False,
    terminal: bool | None = None,
    stdout: Any = None,
    stderr: Any = None,
) -> tuple[Ui, io.StringIO, io.StringIO]:
    """A `Ui` on two `StringIO` streams (O6); ``stdout`` and ``stderr`` replace them when given."""
    out = io.StringIO() if stdout is None else stdout
    err = io.StringIO() if stderr is None else stderr
    ui = Ui(out, err, io.StringIO(), color=color, env={}, terminal=terminal, size=(width, height))
    return ui, out, err


def make_build(build: str) -> Build:
    """A hand-built `Build` matching the golden folder's ``build.toml``."""
    data = tomllib.loads((tlc_folder(build) / "build.toml").read_text(encoding="utf-8"))
    sha256 = str(data["sha256"])
    return Build(
        id=f"{data['tag']}-{sha256[:8]}",
        name=str(data["tag"]),
        commit=str(data["commit"]),
        calver=None if "calver" not in data else str(data["calver"]),
        built_at=None,
        sha256=sha256,
        size=0,
        prerelease=False,
        source=Source("github-release", "https://example.invalid/tla2tools.jar", 1, None, digest_checked=True),
        installed_at="2026-11-15T00:00:00Z",
        capabilities=frozenset(),
        path=tlc_folder(build),
    )


@dataclass
class Case:
    """One golden case and the facts the replay needs about it."""

    build: str
    name: str
    table: dict[str, Any]
    lines: list[str]  # as fed to the parser, folder mapped or not
    captured_folder: str | None  # the folder of the first "Parsing file" line, as captured
    folder: Path  # the case's folder under golden/specs/
    spec: Path
    cfg: Path | None


def _parsing_folder(lines: list[str]) -> tuple[str | None, str | None]:
    """The folder and file name of the first ``Parsing file`` line: the spec SANY read first."""
    for line in lines:
        if line.startswith(_PARSING):
            path = line[len(_PARSING) :].rstrip("\r\n")
            folder, _, name = path.rpartition("/")
            return folder, name
    return None, None


def load_case(build: str, name: str, *, map_folder: bool = True) -> Case:
    folder = tlc_folder(build)
    table = cases_of(folder)[name]
    lines = read_lines(folder / f"{name}.out")
    captured, file_name = _parsing_folder(lines)
    # Research 28's captures keep no spec file; such a spec is named as SANY named it.
    spec = specs_root() / (f"{table['spec']}.tla" if "spec" in table else (file_name or "spec.tla"))
    case_folder = spec.parent
    args = [str(arg) for arg in table.get("args", [])]
    # The cfg as if the user had named it with --cfg: the one -config names, else the one beside the spec; none
    # when that file is not there (tlaup would not have started TLC with a --cfg that does not exist).
    named = args[args.index("-config") + 1] if "-config" in args[:-1] else None
    cfg: Path | None = case_folder / named if named is not None else spec.with_suffix(".cfg")
    if not cfg.is_file():
        cfg = None
    if map_folder and captured is not None:
        old = f"{_PARSING}{captured}/"
        new = f"{_PARSING}{case_folder.as_posix()}/"
        lines = [new + line[len(old) :] if line.startswith(old) else line for line in lines]
    return Case(build, name, table, lines, captured, case_folder, spec, cfg)


def make_run(case: Case, *, override_classes: tuple[str, ...] = ()) -> RunInfo:
    """A fixed `RunInfo`; a case whose arguments carry ``-workers`` passed them after ``--``, so tlaup does not know
    the workers and the header leaves them out (O3)."""
    args = [str(arg) for arg in case.table.get("args", [])]
    return RunInfo(
        tool="tlc",
        spec=case.spec,
        cfg=case.cfg,
        build=make_build(case.build),
        java=JavaRuntime(JavaTool(Path("/usr/bin/java"), "PATH"), JAVA_VERSION, 25, ()),
        workers=None if "-workers" in args else "auto",
        project_root=None,
        override_classes=override_classes,
        command=("java", "tlc2.TLC"),
        cwd=case.folder,
    )


def make_outcome(case: Case, result: RunResult, **changes: Any) -> RunOutcome:
    """The outcome of the case's ``cases.toml``: its exit code, nothing stopped, nothing kept or dropped.

    Two cases of research 2 recorded no exit code; their outcome has no TLC code (``tool_exit_code`` None), so
    the result line shows none rather than a guessed one.
    """
    code = None if "exit" not in case.table else int(case.table["exit"])
    values: dict[str, Any] = {
        "result": result,
        "exit_code": 0 if code is None else code,
        "tool_exit_code": code,
        "stopped_by": None,
        "stderr_tail": (),
        "warnings": (),
        "run_folder_kept": None,
        "resume_command": None,
        "dropped_checkpoint": None,
        "stopped_for_closed_pipe": False,
        "kept": None,
    }
    values.update(changes)
    return RunOutcome(**values)


def stderr_lines(case: Case) -> list[str]:
    """The case's captured stderr file, line by line, when it has one."""
    name = case.table.get("stderr")
    if name is None:
        return []
    return [line.rstrip("\r\n") for line in read_lines(tlc_folder(case.build) / str(name))]


@dataclass
class Replay:
    stdout: str
    stderr: str
    result: RunResult
    reporter: TerminalReporter
    events: list[Event] = field(default_factory=list)


def replay(
    build: str,
    name: str,
    *,
    map_folder: bool = True,
    override_classes: tuple[str, ...] = (),
    width: int = WIDTH,
    height: int = HEIGHT,
    color: bool = False,
    terminal: bool | None = None,
    mode: Literal["plain", "layout"] = "plain",
    stdout: Any = None,
    before_finish: Callable[[RunResult], None] | None = None,
    after_start: Callable[[TerminalReporter], None] | None = None,
    after_event: Callable[[TerminalReporter, Event], None] | None = None,
    **outcome: Any,
) -> Replay:
    """Feed the case to a parser and its events to a reporter, then ``close()``'s events, the captured stderr,
    ``finish`` and ``close``; ``outcome`` changes fields of the `RunOutcome`.

    Plain mode reads a `SecondClock`. Layout mode (package 40) draws no frame by itself (``refresh_thread=False``)
    and reads an `EventClock`, ticked after each event; a layout test also sets ``TERM`` and passes
    ``terminal=True`` (O6, "Drawing without a terminal")."""
    case = load_case(build, name, map_folder=map_folder)
    ui, out, err = make_ui(width=width, height=height, color=color, terminal=terminal, stdout=stdout)
    event_clock = EventClock() if mode == "layout" else None
    clock: Callable[[], float] = SecondClock() if event_clock is None else event_clock
    reporter = TerminalReporter(ui, mode=mode, clock=clock, refresh_thread=False)
    parser = TlcParser()
    events: list[Event] = []
    reporter.start(make_run(case, override_classes=override_classes))
    if after_start is not None:
        after_start(reporter)

    def hand(batch: list[Event]) -> None:
        for event in batch:
            events.append(event)
            reporter.handle(event, parser.result)
            if event_clock is not None:
                event_clock.tick()
            if after_event is not None:
                after_event(reporter, event)

    for line in case.lines:
        hand(parser.feed(line))
    hand(parser.close())
    for line in stderr_lines(case):
        reporter.stderr_line(line)
    if before_finish is not None:
        before_finish(parser.result)
    reporter.finish(make_outcome(case, parser.result, **outcome))
    reporter.close()
    return Replay(out.getvalue(), err.getvalue(), parser.result, reporter, events)


def case_names(build: str) -> list[str]:
    """Every TLC case of the build's ``cases.toml``, the ``plain`` captures left out."""
    return sorted(cases_of(tlc_folder(build)))
