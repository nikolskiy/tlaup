"""TLA+ values as TLC prints them (design 10 P7). This package adds the type; package 11 adds ``parse_value``."""

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
