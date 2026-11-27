"""The SANY output parser (design 10 P8).

``SanyParser`` reads SANY's text one line at a time, gives every line a class and returns each diagnostic once,
when it is complete. It opens no file and knows no command line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, cast

from tlaup_parse.model import Diagnostic, Location

if TYPE_CHECKING:
    from collections.abc import Mapping

    from tlaup_parse.values import JSONObject


class SanyLineClass(Enum):
    """What the parser used a line as. The value is the dictionary form: the name in lower case."""

    BANNER = "banner"
    PROGRESS = "progress"
    HEADER = "header"
    STRUCTURE = "structure"
    POSITION = "position"
    MESSAGE = "message"
    BLANK = "blank"
    OTHER = "other"


@dataclass(frozen=True)
class SanyStep:
    line_class: SanyLineClass | None  # None only from close()
    diagnostics: tuple[Diagnostic, ...]  # usually empty: a diagnostic is returned when it is complete


@dataclass(frozen=True)
class SanyResult:
    diagnostics: tuple[Diagnostic, ...]
    module_files: dict[str, str]
    other: tuple[str, ...]  # the lines of class OTHER, in order
    lines_used: int  # how many input lines had another class

    def to_dict(self) -> dict[str, object]:
        return {
            "diagnostics": [d.to_dict() for d in self.diagnostics],
            "module_files": dict(self.module_files),
            "other": list(self.other),
            "lines_used": self.lines_used,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> SanyResult:
        diagnostics = cast("list[JSONObject]", data["diagnostics"])
        return cls(
            diagnostics=tuple(Diagnostic.from_dict(d) for d in diagnostics),
            module_files=dict(cast("dict[str, str]", data["module_files"])),
            other=tuple(cast("list[str]", data["other"])),
            lines_used=cast("int", data["lines_used"]),
        )


_BANNER = re.compile(r"\*{6} SANY2 Version ")
_PARSING = re.compile(r"Parsing file (.+)")
_JAR_SUFFIX = re.compile(r"(.*?) \(jar:.*\)")
_SEMANTIC = re.compile(r"Semantic processing of module \S+")
_LINTING = re.compile(r"Linting of module \S+")
_LOCATION = re.compile(r"line (\d+), col (\d+) to line (\d+), col (\d+) of module (\w+)")
_AT_LINE = re.compile(r"at line (\d+), column (\d+)")
_FATAL = re.compile(r"Fatal errors while parsing TLA\+ spec in file .+")
_COULD_NOT = re.compile(r"Could not parse module (\S+) from file .+")
_COUNT = re.compile(r"\*\*\* (?:Errors|Abort messages): \d+")
_IN_MODULE = re.compile(r"In module (\S+)")
_WARNING_BLOCK = re.compile(r"Warnings \(\d+\) during syntax parsing of .+:")
_WARNING_LINE = re.compile(r"!! WARNING: (.*)")
_IN_MODULE_TEXT = re.compile(r"in module (\w+)")
_ABORT_EXCEPTION = "tla2sany.semantic.AbortException"
_UNKNOWN_LOCATION = "Unknown location"
_PARSE_ERROR = "***Parse Error***"
_RESIDUAL = "Residual stack trace follows:"
_SEMANTIC_ERRORS = "Semantic errors:"
_NO_FILE = "Cannot find the specified file "

_PARSE_STATES = frozenset({"parse_error", "parse_stack", "parse_tail"})


def _module_of_path(path: str) -> str:
    """The module a ``Parsing file`` path stands for: the file name without its extension, for ``/`` or ``\\``."""
    name = re.split(r"[\\/]", path)[-1]
    stem, dot, _ = name.rpartition(".")
    return stem if dot and stem else name


@dataclass
class _Open:
    """The diagnostic being collected."""

    severity: str
    module: str | None
    location: Location | None
    parse_error: bool = False
    message: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)


class SanyParser:
    """Feeds on SANY's lines and keeps the result so far; see the module docstring and design 10 P8."""

    def __init__(self) -> None:
        self._state = "preamble"
        self._open: _Open | None = None
        self._diagnostics: list[Diagnostic] = []
        self._seen: set[tuple[str, str | None, Location | None, str]] = set()
        self._module_files: dict[str, str] = {}
        self._other: list[str] = []
        self._fed = 0
        self._after_other = False

    @property
    def result(self) -> SanyResult:
        return SanyResult(
            diagnostics=tuple(self._diagnostics),
            module_files=dict(self._module_files),
            other=tuple(self._other),
            lines_used=self._fed - len(self._other),
        )

    def feed(self, line: str) -> SanyStep:
        text = line.rstrip()
        self._fed += 1
        done: list[Diagnostic] = []
        if text:
            line_class = self._classify(text, done)
        elif self._after_other:
            line_class = SanyLineClass.OTHER
        else:
            line_class = SanyLineClass.BLANK
        if line_class is SanyLineClass.OTHER:
            self._other.append(text)
        self._after_other = line_class is SanyLineClass.OTHER
        return SanyStep(line_class, tuple(done))

    def close(self) -> SanyStep:
        done: list[Diagnostic] = []
        self._complete(done)
        self._state = "preamble"
        return SanyStep(None, tuple(done))

    # -- the state machine ---------------------------------------------------------------------------------------

    def _classify(self, text: str, done: list[Diagnostic]) -> SanyLineClass:  # noqa: PLR0911, PLR0912 - one branch per state and line shape
        state = self._state
        if _BANNER.match(text):
            return self._enter("preamble", done, SanyLineClass.BANNER)
        parsing = _PARSING.fullmatch(text)
        if parsing:
            self._complete(done)
            self._state = "preamble"
            self._record_file(parsing.group(1))
            return SanyLineClass.PROGRESS
        if _SEMANTIC.fullmatch(text) or _LINTING.fullmatch(text):
            return self._enter("preamble", done, SanyLineClass.PROGRESS)
        if text == _SEMANTIC_ERRORS:
            return self._enter("semantic_errors", done, SanyLineClass.HEADER)
        located = _LOCATION.fullmatch(text)
        if located and state not in _PARSE_STATES:
            self._complete(done)
            line, col, end_line, end_col, module = located.groups()
            location = Location(module, int(line), int(col), int(end_line), int(end_col))
            self._open = _Open("error", module, location)
            return SanyLineClass.POSITION
        if text == _PARSE_ERROR:
            self._complete(done)
            self._open = _Open("error", None, None, parse_error=True)
            self._state = "parse_error"
            return SanyLineClass.HEADER
        if text == _RESIDUAL and state == "parse_error":
            self._state = "parse_stack"
            return SanyLineClass.HEADER
        if _FATAL.fullmatch(text):
            if state in ("parse_error", "parse_stack"):
                self._state = "parse_tail"
                return SanyLineClass.HEADER
            return self._enter("abort", done, SanyLineClass.HEADER)
        could_not = _COULD_NOT.fullmatch(text)
        if could_not and state == "parse_tail":
            if self._open is not None and self._open.parse_error:
                self._open.module = could_not.group(1)
                self._complete(done)
            return SanyLineClass.STRUCTURE
        if _COUNT.fullmatch(text) or text == _ABORT_EXCEPTION:
            if state != "parse_tail":
                self._complete(done)
            return SanyLineClass.STRUCTURE
        in_module = _IN_MODULE.fullmatch(text)
        if in_module or text == _UNKNOWN_LOCATION:
            if state == "parse_tail":
                return SanyLineClass.STRUCTURE
            if state in ("abort", "warnings"):
                self._complete(done)
                module = in_module.group(1) if in_module else None
                self._open = _Open("error" if state == "abort" else "warning", module, None)
                return SanyLineClass.POSITION
        return self._classify_rest(text, done)

    def _classify_rest(self, text: str, done: list[Diagnostic]) -> SanyLineClass:
        if _WARNING_BLOCK.fullmatch(text):
            return self._enter("warnings", done, SanyLineClass.HEADER)
        warning = _WARNING_LINE.fullmatch(text)
        if warning:
            self._complete(done)
            message = warning.group(1)
            found = _IN_MODULE_TEXT.search(message)
            self._finish(_Open("warning", found.group(1) if found else None, None, message=[message]), done)
            return SanyLineClass.MESSAGE
        if text.startswith(_NO_FILE):
            self._complete(done)
            self._finish(_Open("error", None, None, message=[text]), done)
            return SanyLineClass.MESSAGE
        if self._open is None:
            return SanyLineClass.OTHER
        (self._open.details if self._state == "parse_stack" else self._open.message).append(text)
        return SanyLineClass.MESSAGE

    def _enter(self, state: str, done: list[Diagnostic], line_class: SanyLineClass) -> SanyLineClass:
        self._complete(done)
        self._state = state
        return line_class

    def _record_file(self, path: str) -> None:
        jar = _JAR_SUFFIX.fullmatch(path)
        if jar:
            path = jar.group(1)
        self._module_files[_module_of_path(path)] = path

    # -- completing diagnostics ----------------------------------------------------------------------------------

    def _complete(self, done: list[Diagnostic]) -> None:
        """Return the open diagnostic if it has a message; drop it if it has none."""
        opened, self._open = self._open, None
        if opened is None or not opened.message:
            return
        if opened.parse_error:
            opened.location = _parse_location("\n".join(opened.message), opened.module)
        self._finish(opened, done)

    def _finish(self, item: _Open, done: list[Diagnostic]) -> None:
        message = "\n".join(item.message)
        key = (item.severity, item.module, item.location, message)
        if key in self._seen:
            return
        self._seen.add(key)
        diagnostic = Diagnostic(
            tool="sany",
            severity=item.severity,
            message=message,
            module=item.module,
            file=self._module_files.get(item.module) if item.module is not None else None,
            location=item.location,
            details=tuple(item.details),
        )
        self._diagnostics.append(diagnostic)
        done.append(diagnostic)


def _parse_location(message: str, module: str | None) -> Location | None:
    at = _AT_LINE.search(message)
    if at:
        return Location(module or "", int(at.group(1)), int(at.group(2)), None, None)
    span = _LOCATION.search(message)
    if span:
        line, col, end_line, end_col, where = span.groups()
        return Location(where, int(line), int(col), int(end_line), int(end_col))
    return None
