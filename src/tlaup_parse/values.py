"""TLA+ values as TLC prints them, and their parser (design 10 P7).

``parse_value`` is a recursive-descent parser over one string. It is total: any failure, at any depth, gives
the whole input back as one ``raw`` value, and no exception leaves it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Value:
    kind: str  # "int", "bool", "string", "model", "set", "seq", "record", "function", "interval", "raw"
    text: str = field(compare=False)  # the source text of this value, as printed (always kept); not compared,
    # so two values are equal when their trees are equal
    items: tuple[Value, ...] = ()  # set, seq
    fields: tuple[tuple[str, Value], ...] = ()  # record
    pairs: tuple[tuple[Value, Value], ...] = ()  # function
    scalar: int | bool | str | None = None  # int, bool, string (unescaped), model (its name),
    # raw (the text again, so that two raw values compare by text)
    bounds: tuple[int, int] | None = None  # interval a..b

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "text": self.text,
            "items": [item.to_dict() for item in self.items],
            "fields": [[name, value.to_dict()] for name, value in self.fields],
            "pairs": [[key.to_dict(), value.to_dict()] for key, value in self.pairs],
            "scalar": self.scalar,
            "bounds": None if self.bounds is None else list(self.bounds),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Value:
        bounds = data["bounds"]
        return cls(
            kind=data["kind"],
            text=data["text"],
            items=tuple(cls.from_dict(item) for item in data["items"]),
            fields=tuple((name, cls.from_dict(value)) for name, value in data["fields"]),
            pairs=tuple((cls.from_dict(key), cls.from_dict(value)) for key, value in data["pairs"]),
            scalar=data["scalar"],
            bounds=None if bounds is None else (bounds[0], bounds[1]),
        )


def parse_value(text: str) -> Value:
    """The value TLC printed as ``text``, as a tree; the whole text as one ``raw`` value if it does not parse.

    White space, newlines included, may stand between any two tokens. Forms TLC prints without enumerating
    (``[S -> T]``, ``SUBSET S``, ``{x \\in S : P}``) are not in the grammar and come out ``raw``.
    """
    try:
        parser = _Parser(text)
        value = parser.value()
        parser.end()
    except (_ParseError, ValueError, RecursionError):
        # ValueError: an integer longer than int() reads; RecursionError: nesting deeper than the stack.
        return Value(kind="raw", text=text, scalar=text)
    return value if value.text == text else _with_text(value, text)


class _ParseError(Exception):
    pass


_SPACE = frozenset(" \t\r\n\f\v")
_DIGITS = frozenset("0123456789")
_NAME_START = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
_NAME_REST = _NAME_START | _DIGITS


def _with_text(value: Value, text: str) -> Value:
    return Value(
        kind=value.kind,
        text=text,
        items=value.items,
        fields=value.fields,
        pairs=value.pairs,
        scalar=value.scalar,
        bounds=value.bounds,
    )


class _Parser:
    """The grammar of P7 over one string; ``pos`` is the next character to read."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def error(self) -> _ParseError:
        return _ParseError(self.pos)

    def skip(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in _SPACE:
            self.pos += 1

    def peek(self, token: str) -> bool:
        """Whether ``token`` comes next, after white space (which is skipped)."""
        self.skip()
        return self.text.startswith(token, self.pos)

    def take(self, token: str) -> bool:
        if self.peek(token):
            self.pos += len(token)
            return True
        return False

    def expect(self, token: str) -> None:
        if not self.take(token):
            raise self.error()

    def end(self) -> None:
        self.skip()
        if self.pos != len(self.text):
            raise self.error()

    def value(self) -> Value:
        self.skip()
        start = self.pos
        char = self.text[start : start + 1]
        if char == "-" or char in _DIGITS:
            return self.number(start)
        if char == '"':
            return self.string(start)
        if char in _NAME_START:
            name = self.name()
            if name in {"TRUE", "FALSE"}:
                return Value(kind="bool", text=name, scalar=name == "TRUE")
            return Value(kind="model", text=name, scalar=name)
        return self.collection(start)

    def collection(self, start: int) -> Value:
        """A set, sequence, record or function: the forms that open with a bracket."""
        if self.take("{"):
            items = self.listed("}")
            return Value(kind="set", text=self.text[start : self.pos], items=items)
        if self.take("<<"):
            items = self.listed(">>")
            return Value(kind="seq", text=self.text[start : self.pos], items=items)
        if self.take("["):
            return self.record(start)
        if self.take("("):
            return self.function(start)
        raise self.error()

    def integer(self) -> int:
        start = self.pos
        if self.text.startswith("-", start):
            self.pos += 1
        digits = self.pos
        while self.pos < len(self.text) and self.text[self.pos] in _DIGITS:
            self.pos += 1
        if self.pos == digits:
            raise self.error()
        return int(self.text[start : self.pos])

    def number(self, start: int) -> Value:
        low = self.integer()
        after = self.pos
        if self.take(".."):
            self.skip()
            high = self.integer()
            return Value(kind="interval", text=self.text[start : self.pos], bounds=(low, high))
        self.pos = after
        return Value(kind="int", text=self.text[start : self.pos], scalar=low)

    def string(self, start: int) -> Value:
        """A quoted string. Only ``\\"`` and ``\\\\`` are escapes; any other backslash is an odd form and fails.

        Characters inside the quotes, newlines and non-ASCII ones included, are kept as they are.
        """
        self.pos += 1
        chars: list[str] = []
        while self.pos < len(self.text):
            char = self.text[self.pos]
            if char == '"':
                self.pos += 1
                return Value(kind="string", text=self.text[start : self.pos], scalar="".join(chars))
            if char == "\\":
                char = self.text[self.pos + 1 : self.pos + 2]
                if char not in {'"', "\\"}:
                    break
                self.pos += 1
            chars.append(char)
            self.pos += 1
        raise self.error()

    def name(self) -> str:
        self.skip()
        start = self.pos
        if self.text[start : start + 1] not in _NAME_START:
            raise self.error()
        self.pos += 1
        while self.pos < len(self.text) and self.text[self.pos] in _NAME_REST:
            self.pos += 1
        return self.text[start : self.pos]

    def listed(self, close: str) -> tuple[Value, ...]:
        """Values separated by commas up to ``close``, which is consumed; none at all is allowed."""
        if self.take(close):
            return ()
        items = [self.value()]
        while self.take(","):
            items.append(self.value())
        self.expect(close)
        return tuple(items)

    def record(self, start: int) -> Value:
        fields: list[tuple[str, Value]] = []
        while True:
            name = self.name()
            self.expect("|->")
            fields.append((name, self.value()))
            if not self.take(","):
                break
        self.expect("]")
        return Value(kind="record", text=self.text[start : self.pos], fields=tuple(fields))

    def function(self, start: int) -> Value:
        pairs: list[tuple[Value, Value]] = []
        while True:
            key = self.value()
            self.expect(":>")
            pairs.append((key, self.value()))
            if not self.take("@@"):
                break
        self.expect(")")
        return Value(kind="function", text=self.text[start : self.pos], pairs=tuple(pairs))
