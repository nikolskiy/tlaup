"""The full-screen layout of the live display (design 22 O4): four panels drawn from one frozen `LayoutView`.

`render_layout` is pure: the reporter's refresh thread calls it with the current view and the clock, and the
snapshot tests call it directly (O6). The view holds everything a frame needs and is replaced whole on each event,
never changed in place, so the thread needs no lock. The Output panel cuts a line wider than the panel with an
ellipsis; the full line is in the reporter's spool. The other panels hold tlaup's own short lines and the header,
cut the same way only on a terminal too narrow for them (the header is in the scrollback in full).
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.console import Group
from rich.layout import Layout
from rich.padding import Padding
from rich.text import Text

from tlaup.reporters.text import format_count, progress_line
from tlaup_parse import Phase

if TYPE_CHECKING:
    from rich.console import RenderableType

    from tlaup.reporters.base import RunInfo
    from tlaup_parse import Progress

MIN_WIDTH = 60  # the smallest terminal the layout is drawn on (O4); smaller gets plain output
MIN_HEIGHT = 15
PROGRESS_KEPT = 50  # the newest progress rows a view holds (O7)
TAIL_KEPT = 200  # the newest output and stderr lines a view holds (O7)
STATUS_HEIGHT = 4  # its title and three lines
HINT = "Ctrl-C to interrupt"
STDERR_MARK = "stderr: "

_PHASE_WORDS = {
    Phase.NOT_STARTED: "Starting",
    Phase.STARTING: "Starting",
    Phase.PARSING: "Parsing",
    Phase.INITIAL_STATES: "Computing initial states",
    Phase.CHECKING: "Checking",
    Phase.LIVENESS: "Checking liveness",
    Phase.FINISHED: "Finished",
}
_INTERRUPTED = "Interrupted"
_RULE = "─"
_PROGRESS_COLUMNS = ("Time", "Diameter", "Generated", "Distinct", "Queue")
_TIME_WIDTH = len("2026-11-14 22:26:59")  # TLC's progress time
_NUMBER_WIDTH = len("1,234,567,890,123")  # 13 digits with their separators
_MARGIN = " "  # one column at each side, as in O4's mock-up


@dataclass(frozen=True)
class LayoutView:
    """Everything a frame needs; replaced whole on each event."""

    run: RunInfo
    phase: Phase
    started_at: float  # the reporter's clock
    errors: int
    warnings: int
    progress: tuple[Progress, ...]  # newest 50
    tail: tuple[Text, ...]  # newest 200 lines of the result text and of TLC's stderr
    notice: str | None = None  # the waiting line (O1), shown in place of the hint
    header: tuple[Text, ...] = ()  # the header lines: two, or three with TLC's version line
    interrupted: bool = False  # finish got an outcome stopped by a signal


def format_clock(seconds: float) -> str:
    """``00:02:13``: the Status panel's elapsed time, whole seconds; hours past 99 keep their digits."""
    whole = max(0, int(seconds))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02}:{minutes:02}:{secs:02}"


def phase_word(view: LayoutView) -> str:
    """``Checking``; ``Interrupted`` once a signal stopped the run; ``Starting`` before TLC reports a phase."""
    return _INTERRUPTED if view.interrupted else _PHASE_WORDS[view.phase]


def _cut(line: Text, width: int) -> Text:
    """One line, never wrapped, cut with an ellipsis when wider than ``width`` (tabs as the terminal shows them)."""
    text = line.copy()
    text.expand_tabs()
    text.no_wrap = True
    text.overflow = "ellipsis"
    text.end = ""
    text.truncate(width, overflow="ellipsis")
    return text


def _title(name: str, width: int) -> Text:
    """``── Status ───────``, across the panel."""
    start = f"{_RULE * 2} {name} "
    return Text(start + _RULE * max(0, width - len(start)), no_wrap=True, overflow="crop", end="")


def _status_line(view: LayoutView, now: float, inner: int) -> Text:
    """``Checking            elapsed 00:02:13            errors 0   warnings 1``: the phase at the left, the counts
    at the right, the elapsed time centred between them; on a narrow screen the phase word is cut first."""
    middle = f"elapsed {format_clock(now - view.started_at)}"
    right = f"errors {view.errors}   warnings {view.warnings}"
    gap = 2
    right_at = max(0, inner - len(right))
    middle_at = max(0, min((inner - len(middle)) // 2, right_at - gap - len(middle)))
    phase = _cut(Text(phase_word(view)), max(0, middle_at - gap)).plain
    line = f"{phase:<{middle_at}}{middle}"
    return _cut(Text(f"{line:<{right_at}}{right}"), inner)


def _status(view: LayoutView, now: float, inner: int) -> Group:
    latest = progress_line(view.progress[-1]) if view.progress else ""
    hint = view.notice if view.notice is not None else HINT
    rows = [_title("Status", inner), _status_line(view, now, inner), _cut(Text(latest), inner), _cut(Text(hint), inner)]
    return Group(*(_padded(row) for row in rows))


def _padded(renderable: RenderableType) -> RenderableType:
    return Padding(renderable, (0, len(_MARGIN)))


def _count(value: int) -> str:
    return format_count(value) if value >= 0 else ""  # TLC gives -1 for a count it does not know (simulation)


@functools.cache
def progress_widths(inner: int) -> tuple[tuple[int, ...], int]:
    """The widths of the progress columns and the gap between them, from the screen's width alone, so that the
    headings and the numbers stay where they are as counts grow. A number column holds 13 digits with their
    separators where the screen has room, less on a narrow one; the gap is at least 2 columns, or 1 when that
    leaves the numbers more room."""
    headings = _PROGRESS_COLUMNS[1:]
    room = 0  # the most a number column gets
    for gap in (2, 1):
        for candidate in range(_NUMBER_WIDTH, room, -1):
            if _TIME_WIDTH + gap * len(headings) + sum(max(len(name), candidate) for name in headings) <= inner:
                room = candidate
                break
    widths = (_TIME_WIDTH, *(max(len(name), room) for name in headings))
    spare = inner - sum(widths)
    return widths, max(1, spare // len(headings))


def _progress(view: LayoutView, inner: int, height: int) -> Group:
    """The title, the column headings and the newest rows that fit; the numbers right-aligned, the spare width
    shared between the columns."""
    count = max(0, height - 2)  # the title and the column headings
    shown = view.progress[-count:] if count else ()
    rows = [_PROGRESS_COLUMNS] + [
        (item.at, _count(item.diameter), _count(item.generated), _count(item.distinct), _count(item.queue))
        for item in shown
    ]
    widths, gap = progress_widths(inner)
    lines = [_title("State space progress", inner)]
    for row in rows:
        cells = [row[0].ljust(widths[0])] + [cell.rjust(width) for cell, width in zip(row[1:], widths[1:], strict=True)]
        lines.append(_cut(Text((" " * gap).join(cells)), inner))
    return Group(*(_padded(line) for line in lines))


def _output(view: LayoutView, inner: int, height: int) -> Group:
    rows = max(0, height - 1)
    shown = list(view.tail[-rows:]) if rows else []
    return Group(_padded(_title("Output", inner)), *(_padded(_cut(line, inner)) for line in shown))


def progress_height(height: int) -> int:
    """The State space progress panel's lines: a third of the screen."""
    return height // 3


def render_layout(view: LayoutView, now: float, width: int, height: int) -> RenderableType:
    """The four panels on Rich's `Layout`: Header, Status, State space progress, Output (O4's mock-up)."""
    inner = max(0, width - 2 * len(_MARGIN))
    header = Layout(Group(*(_padded(_cut(line, inner)) for line in view.header)), size=len(view.header))
    status = Layout(_status(view, now, inner), size=STATUS_HEIGHT)
    lines = progress_height(height)
    progress = Layout(_progress(view, inner, lines), size=lines)
    rest = max(0, height - len(view.header) - STATUS_HEIGHT - lines)
    output = Layout(_output(view, inner, rest), ratio=1)
    root = Layout()
    root.split_column(header, status, progress, output)
    return root
