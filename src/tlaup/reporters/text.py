"""The pure text functions of the terminal reporter (design 22 O3) and of `tlaup sany` (21 S1).

Each takes values and returns strings or a Rich `Text`; none reads a file, a clock or the environment. The
editor form of a diagnostic and the source excerpt under it are here, not in `terminal.py`, so that `tlaup sany`
prints a diagnostic the same way without importing the reporter (S1, decision D66).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from rich.text import Text

from tlaup.durations import format_elapsed
from tlaup_parse import ErrorKind, Verdict, describe_exit_status

if TYPE_CHECKING:
    from tlaup.tlc.runner import RunOutcome
    from tlaup_parse import Diagnostic, FinalStats, Location, Progress, RunResult, Value

# --- Counts, paths, progress and statistics ------------------------------------------------------------------------


def format_count(n: int, *, approximate: bool = False) -> str:
    """``1,771,600``; ``about 1,771,600`` for a count that may be off (a resumed run, D54)."""
    text = f"{n:,}"
    return f"about {text}" if approximate else text


def format_path(path: Path | str, cwd: Path) -> str:
    """The path relative to ``cwd`` when it is beneath it, else as given (absolute in a real run; S1)."""
    candidate = Path(path)
    if candidate.is_absolute() and candidate.is_relative_to(cwd):
        return str(candidate.relative_to(cwd))
    return str(path)


def progress_line(p: Progress) -> str:
    """``44 states generated, 44 distinct, 35 on queue, diameter 4``; a count TLC gives as -1 is left out (P3)."""
    parts = []
    if p.generated >= 0:
        parts.append(f"{format_count(p.generated)} states generated")
    if p.distinct >= 0:
        parts.append(f"{format_count(p.distinct)} distinct")
    if p.queue >= 0:
        parts.append(f"{format_count(p.queue)} on queue")
    if p.diameter >= 0:
        parts.append(f"diameter {format_count(p.diameter)}")
    return ", ".join(parts)


def stats_line(s: FinalStats, *, approximate: bool) -> str:
    """``44 states generated, 44 distinct, 35 left on queue; depth 4``; a part TLC did not print is left out."""
    parts = []
    if s.total_states is not None and s.total_states >= 0:
        parts.append(f"{format_count(s.total_states, approximate=approximate)} states generated")
    if s.distinct_states is not None and s.distinct_states >= 0:
        parts.append(f"{format_count(s.distinct_states, approximate=approximate)} distinct")
    if s.queue is not None and s.queue >= 0:
        parts.append(f"{format_count(s.queue, approximate=approximate)} left on queue")
    counts = ", ".join(parts)
    if s.state_depth is None:
        return counts
    depth = f"depth {format_count(s.state_depth)}"
    return f"{counts}; {depth}" if counts else depth


# --- Diagnostics: the editor form and the source excerpt (21 S1, D22, D66) ---------------------------------------

_GUTTER = "  {number:>4} | "
_EMPTY_GUTTER = "  " + " " * 4 + " | "


def _gutter(number: int) -> str:
    return _GUTTER.format(number=number)


def source_excerpt(text: str, location: Location) -> list[str]:
    """The lines of ``text`` around ``location``, with ``^`` marks under its columns (S1, decision D66).

    The two lines before the location's first line, that line, the marks, ``Error here: ...``, the rest of the
    location's lines, and the two lines after its last; nothing when the first line is not in ``text``.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()  # the text's last newline ends a line; it does not start one
    first = location.line
    if first < 1 or first > len(lines):
        return []
    has_end = location.end_line is not None and location.end_column is not None
    last = min(max(location.end_line or first, first), len(lines)) if has_end else first
    line = lines[first - 1]
    column = max(location.column, 1)
    if not has_end:
        marks = 1
        where = f"line {first}, col {location.column}"
    elif location.end_line == first:
        end_column = location.end_column or column
        marks = max(end_column - column + 1, 1)
        where = f"line {first}, col {location.column} to {location.end_column}"
    else:
        marks = max(len(line) - column + 1, 1)
        where = f"line {first}, col {location.column} to line {location.end_line}, col {location.end_column}"
    pad = "".join("\t" if char == "\t" else " " for char in line[: column - 1])
    pad += " " * (column - 1 - len(pad))
    out = [_gutter(n) + lines[n - 1] for n in range(max(first - 2, 1), first + 1)]
    out.append(_EMPTY_GUTTER + pad + "^" * marks)
    out.append(_EMPTY_GUTTER + "Error here: " + where)
    out.extend(_gutter(n) + lines[n - 1] for n in range(first + 1, min(last + 2, len(lines)) + 1))
    return out


def format_diagnostic(d: Diagnostic, *, cwd: Path, spec: Path, source_text: str | None) -> list[str]:
    """The editor-form line, the source excerpt when ``source_text`` holds the location, then the details (S1).

    The path is the file SANY announced for the diagnostic's module, or the spec's own path when none was.
    """
    path = format_path(d.file if d.file is not None else spec, cwd)
    where = "" if d.location is None else f":{d.location.line}:{d.location.column}"
    lines = [f"{path}{where}: {d.severity}: {d.message}"]
    if source_text is not None and d.location is not None:
        lines.extend(source_excerpt(source_text, d.location))
    lines.extend(f"  {detail}" for detail in d.details)
    return lines


# --- The result line (22 O3's table, decisions D54 and D63) -------------------------------------------------------

DROPPED_CHECKPOINT = {
    "not-asked": "a checkpoint was not kept (use --keep to keep one)",
    "incomplete": "the checkpoint was incomplete, nothing to resume",
    "depth-first": "a -dfid run cannot be resumed",
}
_BOUNDED = {"simulate": "simulation", "depth-first": "depth-first"}
_NOT_CHECKED = {
    ErrorKind.PARSE: "the spec has errors",
    ErrorKind.CONFIG: "the configuration has errors",
    ErrorKind.USAGE: "TLC refused its arguments",
    ErrorKind.EXCEPTION: "TLC failed before computing the initial states",
    ErrorKind.OTHER: "TLC failed before computing the initial states",
}
_POSTCONDITION_CODE = 10


def _meaning(code: int, result: RunResult) -> str:
    """X1's sentence for the code, without its full stop and with a lower-case first letter unless the first word
    is an acronym (finding G5); code 10 after a false postcondition says so (O3)."""
    if code == _POSTCONDITION_CODE and result.errors and result.errors[0].kind is ErrorKind.POSTCONDITION:
        return "a postcondition was false"
    sentence = describe_exit_status(code).meaning.removesuffix(".")
    first_word = sentence.split(" ", 1)[0]
    if len(first_word) > 1 and first_word.isupper():
        return sentence
    return sentence[:1].lower() + sentence[1:]


def _code(outcome: RunOutcome, result: RunResult) -> str:
    code = outcome.tool_exit_code
    if code is None:
        return ""
    if code == 0:
        return " (TLC exit code 0)"
    return f" (TLC exit code {code}: {_meaning(code, result)})"


def _not_checked(result: RunResult) -> str:
    if result.errors:
        return _NOT_CHECKED.get(result.errors[0].kind, "")
    if any(d.severity == "error" for d in result.sany):
        return _NOT_CHECKED[ErrorKind.PARSE]
    return ""


def result_line(outcome: RunOutcome, result: RunResult, elapsed: float) -> str:
    """``Result: errors found (TLC exit code 12: an invariant was violated) in 0.7 s`` and the other rows of O3.

    ``elapsed`` is the reporter's own clock from ``start`` to ``finish``; TLC's own duration is used when it gave
    one, except for an interrupted run, which says how long it ran.
    """
    duration = format_elapsed(result.duration_ms / 1000 if result.duration_ms is not None else elapsed)
    code = _code(outcome, result)
    verdict = result.verdict
    if verdict is Verdict.ERRORS:
        line = f"errors found{code} in {duration}"
    elif verdict is Verdict.NO_ERROR:
        line = f"no error found, every state checked{code} in {duration}"
    elif verdict is Verdict.NO_ERROR_BOUNDED:
        search = _BOUNDED.get(result.mode or "")
        named = f" ({search})" if search else ""
        line = f"no error found in a bounded search{named}{code} in {duration}"
    elif verdict is Verdict.NOT_CHECKED:
        reason = _not_checked(result)
        line = f"not checked: {reason}{code}" if reason else f"not checked{code}"
    elif outcome.stopped_by is not None:
        line = f"incomplete, interrupted after {format_elapsed(elapsed)}"
    elif outcome.stopped_for_closed_pipe:
        line = "incomplete, stopped because the output was closed"
    else:
        line = f"incomplete, TLC stopped without finishing{code}"
    if result.resumed:
        line += "; resumed from a checkpoint"
        if result.counts_approximate:
            line += ", state counts approximate"
    if outcome.dropped_checkpoint in DROPPED_CHECKPOINT:
        line += f"; {DROPPED_CHECKPOINT[outcome.dropped_checkpoint]}"
    return f"Result: {line}"


# --- The value diff (O2: kept, rewritten against Value) -----------------------------------------------------------


@dataclass(frozen=True)
class ValueDiff:
    """How a value differs from the one before: whether it changed, and where in its text.

    ``spans`` are ``(start, end)`` offsets into ``new.text`` of the parts that changed: the deepest children that
    differ, the items added to a set or to the end of a sequence, or the whole text when nothing narrower is known.
    """

    changed: bool
    spans: tuple[tuple[int, int], ...]


def _find(text: str, part: str, start: int) -> int:
    found = text.find(part, start)
    if found < 0:
        raise LookupError(part)
    return found


def _children(value: Value) -> list[tuple[object, Value, int]]:
    """Each child with a key to match it by and its offset in ``value.text``, found in order.

    ``Value`` keeps each node's text but no offsets (P7), so a child is looked for after the one before it, a
    record field after its name and ``|->``, a function's value after its key and ``:>``.
    """
    text = value.text
    found: list[tuple[object, Value, int]] = []
    pos = 0
    if value.kind == "record":
        for name, child in value.fields:
            pos = _find(text, "|->", _find(text, name, pos) + len(name)) + 3
            pos = _find(text, child.text, pos)
            found.append((name, child, pos))
            pos += len(child.text)
    elif value.kind == "function":
        for key, child in value.pairs:
            pos = _find(text, ":>", _find(text, key.text, pos) + len(key.text)) + 2
            pos = _find(text, child.text, pos)
            found.append((key, child, pos))
            pos += len(child.text)
    elif value.kind in {"set", "seq"}:
        for index, child in enumerate(value.items):
            pos = _find(text, child.text, pos)
            found.append((index, child, pos))
            pos += len(child.text)
    return found


def _counterparts(old: Value, new: Value) -> list[Value] | None:
    """The children of ``old`` that stand where the children of ``new`` stand, when the two have one shape: a record
    with the same field names, a function with the same keys, a sequence of the same length; else None."""
    if new.kind == "record" and [n for n, _ in old.fields] == [n for n, _ in new.fields]:
        return [value for _, value in old.fields]
    if new.kind == "function" and [k for k, _ in old.pairs] == [k for k, _ in new.pairs]:
        return [value for _, value in old.pairs]
    if new.kind == "seq" and len(old.items) == len(new.items):
        return list(old.items)
    return None


def _added(old: Value, new: Value) -> set[int] | None:
    """The positions of the children ``new`` adds to ``old``: items appended to a sequence, members added to a set
    that lost none; else None."""
    if new.kind == "seq" and len(new.items) > len(old.items) and new.items[: len(old.items)] == old.items:
        return set(range(len(old.items), len(new.items)))
    if new.kind == "set" and all(item in new.items for item in old.items):
        return {index for index, item in enumerate(new.items) if item not in old.items}
    return None


def _spans(old: Value, new: Value, base: int) -> list[tuple[int, int]]:
    if old == new:
        return []
    whole = [(base, base + len(new.text))]
    if old.kind != new.kind:
        return whole
    try:
        children = _children(new)
    except LookupError:
        return whole
    counterparts = _counterparts(old, new)
    if counterparts is not None:
        spans: list[tuple[int, int]] = []
        for before, (_, child, at) in zip(counterparts, children, strict=True):
            spans.extend(_spans(before, child, base + at))
        return spans
    added = _added(old, new)
    if added is not None:
        return [(base + at, base + at + len(child.text)) for i, (_, child, at) in enumerate(children) if i in added]
    return whole


def diff_values(old: Value | None, new: Value) -> ValueDiff:
    """Whether ``new`` differs from ``old`` (``Value`` equality; a ``raw`` value compares as text, P7), and where.

    With no value before (``None``) the whole value is new.
    """
    if old is None:
        return ValueDiff(changed=True, spans=((0, len(new.text)),))
    if old == new:
        return ValueDiff(changed=False, spans=())
    return ValueDiff(changed=True, spans=tuple(_spans(old, new, 0)) or ((0, len(new.text)),))


def render_value_diff(text: str, diff: ValueDiff, style: str) -> Text:
    """``text`` (the value as TLC printed it) as a `Text` with the changed parts in ``style``."""
    rendered = Text(text)
    for start, end in diff.spans:
        rendered.stylize(style, start, end)
    return rendered
