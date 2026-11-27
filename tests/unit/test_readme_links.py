"""The README is also the PyPI page, where a relative link is dead (design 30 B3)."""

from __future__ import annotations

import re
from pathlib import Path

README = Path(__file__).resolve().parents[2] / "README.md"
# Inline [text](target "title") and images; reference definitions "[id]: target"; raw HTML src= and href=.
INLINE = re.compile(r"\]\(\s*<?([^)\s>]+)")
REFERENCE = re.compile(r"^ {0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)", re.MULTILINE)
HTML = re.compile(r"""\b(?:src|href)\s*=\s*["']?([^"'\s>]+)""", re.IGNORECASE)


def relative_links(text: str) -> list[str]:
    """Link targets that are neither an absolute https:// address nor an in-page anchor."""
    targets = [t for pattern in (INLINE, REFERENCE, HTML) for t in pattern.findall(text)]
    return [t for t in targets if not t.startswith(("https://", "#"))]


def test_readme_links_are_absolute() -> None:
    assert relative_links(README.read_text(encoding="utf-8")) == []


def test_a_relative_inline_link_is_found() -> None:
    text = "See [the examples](docs/examples/), [site](https://example.org/x) and [top](#usage)."
    assert relative_links(text) == ["docs/examples/"]


def test_a_relative_reference_definition_is_found() -> None:
    text = "See [a][1].\n\n[1]: docs/x\n[2]: https://example.org/y\n[3]: #top\n"
    assert relative_links(text) == ["docs/x"]


def test_a_relative_html_attribute_is_found() -> None:
    text = '<img src="docs/logo.png"> <a href=\'docs/y\'>y</a> <a href="https://example.org">z</a> <a href="#t">t</a>'
    assert relative_links(text) == ["docs/logo.png", "docs/y"]
