"""The PlusCal translator's output parser (design 10 P2, 21 S2).

``PcalParser`` reads the translator's text one line at a time and keeps what it recognises: the version, the files
it says it wrote, the labels it added and its errors as diagnostics. Every other line is kept, in order. It opens
no file and knows no command line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

from tlaup_parse.model import Diagnostic, Location

if TYPE_CHECKING:
    from collections.abc import Mapping


@dataclass
class PcalResult:
    version: str | None = None
    files_written: list[str] = field(default_factory=list)  # from "New file X written."
    labels_added: list[tuple[str, int, int]] = field(default_factory=list)  # (name, line, column)
    diagnostics: list[Diagnostic] = field(default_factory=list)  # tool="pcal"
    other: list[str] = field(default_factory=list)  # lines not recognised, kept

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "files_written": list(self.files_written),
            "labels_added": [[name, line, column] for name, line, column in self.labels_added],
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "other": list(self.other),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> PcalResult:
        labels = cast("list[list[Any]]", data["labels_added"])
        diagnostics = cast("list[dict[str, Any]]", data["diagnostics"])
        return cls(
            version=cast("str | None", data["version"]),
            files_written=list(cast("list[str]", data["files_written"])),
            labels_added=[(str(name), int(line), int(column)) for name, line, column in labels],
            diagnostics=[Diagnostic.from_dict(d) for d in diagnostics],
            other=list(cast("list[str]", data["other"])),
        )


_BANNER = re.compile(r"pcal\.trans Version (.+)")
_NEW_FILE = re.compile(r"New file (.+) written\.")
_LABELS_HEADING = re.compile(r"The following labels? (?:was|were) added:")
_LABEL = re.compile(r"\s*(\S+) at line (\d+), column (\d+)")
_LOCATION = re.compile(r"\s*(?:at )?line (\d+), column (\d+)\.")
_PROGRESS = frozenset({"Parsing completed.", "Translation completed."})
_ERROR_HEADING = "Unrecoverable error:"
_MESSAGE_PREFIX = " -- "


class PcalParser:
    """Feeds on the translator's lines and keeps the result so far; see the module docstring and design 21 S2."""

    def __init__(self) -> None:
        self._result = PcalResult()
        self._open: str | None = None  # the message of the diagnostic being collected
        self._fresh = False  # the open diagnostic's message line was the previous line
        self._after_error = False  # the previous line was "Unrecoverable error:"
        self._in_labels = False
        self._after_other = False

    @property
    def result(self) -> PcalResult:
        return self._result

    def feed(self, line: str) -> list[Diagnostic]:
        text = line.rstrip()
        fresh, after_error = self._fresh, self._after_error
        self._fresh = self._after_error = False
        done: list[Diagnostic] = []
        was_other, self._after_other = self._after_other, False
        if not text:
            self._complete(None, done)
            self._in_labels = False
            if was_other:
                self._keep(text)
            return done
        if self._in_labels:
            label = _LABEL.fullmatch(text)
            if label:
                self._result.labels_added.append((label.group(1), int(label.group(2)), int(label.group(3))))
                return done
            self._in_labels = False
        if fresh and self._open is not None:
            located = _LOCATION.fullmatch(text)
            if located:
                self._complete(Location("", int(located.group(1)), int(located.group(2)), None, None), done)
                return done
        self._complete(None, done)
        if after_error and text.startswith(_MESSAGE_PREFIX):
            self._open = text[len(_MESSAGE_PREFIX) :]
            self._fresh = True
            return done
        if not self._recognise(text):
            self._keep(text)
        return done

    def close(self) -> list[Diagnostic]:
        done: list[Diagnostic] = []
        self._complete(None, done)
        self._in_labels = False
        return done

    def _recognise(self, text: str) -> bool:
        banner = _BANNER.fullmatch(text)
        if banner:
            self._result.version = banner.group(1)
            return True
        if text in _PROGRESS:
            return True
        written = _NEW_FILE.fullmatch(text)
        if written:
            self._result.files_written.append(written.group(1))
            return True
        if _LABELS_HEADING.fullmatch(text):
            self._in_labels = True
            return True
        if text == _ERROR_HEADING:
            self._after_error = True
            return True
        return False

    def _keep(self, text: str) -> None:
        self._result.other.append(text)
        self._after_other = True

    def _complete(self, location: Location | None, done: list[Diagnostic]) -> None:
        """Finish the open diagnostic, if any: return it and add it to the result."""
        message, self._open = self._open, None
        if message is None:
            return
        diagnostic = Diagnostic(
            tool="pcal", severity="error", message=message, module=None, file=None, location=location
        )
        self._result.diagnostics.append(diagnostic)
        done.append(diagnostic)
