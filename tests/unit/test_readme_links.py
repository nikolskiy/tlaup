"""The README is also the PyPI page, where a relative link is dead (design 30 B3)."""

from __future__ import annotations

import re
from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"
# [text](target), or [text](target "title"); an image is the same shape behind a "!".
LINK = re.compile(r"\]\(\s*<?([^)\s>]+)")


def relative_links(text: str) -> list[str]:
    """Link targets that are neither an absolute https:// address nor an in-page anchor."""
    return [t for t in LINK.findall(text) if not (t.startswith(("https://", "#")))]


def test_readme_links_are_absolute() -> None:
    assert relative_links(README.read_text(encoding="utf-8")) == []


def test_a_relative_link_is_found() -> None:
    text = "See [the examples](docs/examples/), [site](https://example.org/x) and [top](#usage)."
    assert relative_links(text) == ["docs/examples/"]
