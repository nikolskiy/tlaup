"""Lines to plain text and framed TLC messages, and back (design 10 P4).

``Framer`` takes one line per call and returns the top-level items it completed: an ``Unframed`` line outside
every message, or a ``TlcMessage`` with the messages nested in it in its ``body``. ``render_framed`` writes an
item back as the lines it was built from, so rendering everything ``feed`` and ``close`` returned gives the
input lines without their line endings (decision D9). Nothing here decides what a message means; that is
interpretation (P4, rules 1 to 4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from tlaup_parse.codes import CODES
from tlaup_parse.model import TlcMessage

# A number written without leading zeros, so that the integer is written back as it was read. ASCII digits only:
# ``\d`` would take other scripts' digits, which ``str(int(...))`` does not give back.
_N = r"0|[1-9][0-9]*"
# Recognised only at the end of a line; the text in front is the message's ``before``.
START_MARKER = re.compile(rf"^(?P<before>.*)@!@!@STARTMSG (?P<code>{_N}):(?P<sev>{_N}) @!@!@\Z")
# Recognised only at the start of a line, and only when its code is open; the text behind is ``after``.
END_MARKER = re.compile(rf"^@!@!@ENDMSG (?P<code>{_N}) @!@!@(?P<after>.*)\Z")


@dataclass(frozen=True)
class Unframed:
    """A line outside every message, without its line ending."""

    line: str


@dataclass
class _Open:
    code: int
    severity: int
    before: str
    body: list[str | TlcMessage] = field(default_factory=list)

    def closed(self, *, after: str = "", truncated: bool = False) -> TlcMessage:
        info = CODES.get(self.code)
        return TlcMessage(
            code=self.code,
            severity=self.severity,
            name=None if info is None else info.name,
            body=tuple(self.body),
            before=self.before,
            after=after,
            truncated=truncated,
        )


def _without_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return line[:-2]
    return line.removesuffix("\n")


def _number(text: str) -> int | None:
    """The marker's number, or ``None`` when it is too long for ``int`` to read (a line, not a marker)."""
    try:
        return int(text)
    except ValueError:
        return None


class Framer:
    """Frames TLC's ``-tool`` output one line at a time; keeps only the messages still open."""

    def __init__(self) -> None:
        self._open: list[_Open] = []

    def feed(self, line: str) -> list[Unframed | TlcMessage]:
        """Take one line, with or without its ``\\n`` or ``\\r\\n``; return the top-level items it completed."""
        text = _without_ending(line)
        start = START_MARKER.match(text)
        if start is not None:
            code, severity = _number(start["code"]), _number(start["sev"])
            if code is not None and severity is not None:
                self._open.append(_Open(code, severity, start["before"]))
                return []
        end = END_MARKER.match(text)
        if end is not None:
            code = _number(end["code"])
            depth = next((i for i in range(len(self._open) - 1, -1, -1) if self._open[i].code == code), None)
            if depth is not None:
                while len(self._open) > depth + 1:
                    self._deliver(self._open.pop().closed(truncated=True))
                return self._deliver(self._open.pop().closed(after=end["after"]))
        if self._open:
            self._open[-1].body.append(text)
            return []
        return [Unframed(text)]

    def close(self) -> list[Unframed | TlcMessage]:
        """End of input: close every open message ``truncated``, innermost first; return the top-level one."""
        done: list[Unframed | TlcMessage] = []
        while self._open:
            done.extend(self._deliver(self._open.pop().closed(truncated=True)))
        return done

    def _deliver(self, message: TlcMessage) -> list[Unframed | TlcMessage]:
        """Put a closed message into its parent's body in its place, or return it when it is top-level."""
        if self._open:
            self._open[-1].body.append(message)
            return []
        return [message]


def render_framed(item: Unframed | TlcMessage) -> list[str]:
    """The input lines the item was built from, without their line endings (P4)."""
    if isinstance(item, Unframed):
        return [item.line]
    lines = [f"{item.before}@!@!@STARTMSG {item.code}:{item.severity} @!@!@"]
    for part in item.body:
        if isinstance(part, str):
            lines.append(part)
        else:
            lines.extend(render_framed(part))
    if not item.truncated:
        lines.append(f"@!@!@ENDMSG {item.code} @!@!@{item.after}")
    return lines
