"""The exact rebuild over generated line sequences (design 01 T7, last paragraph; 10 P4).

The strategy writes the marker text literally: 01 T12 rule 3 exempts Hypothesis strategies, and this file is
excluded from the ``no-typed-tool-output`` hook by its exact path. Codes are small so that ends often match an
open start. ``event`` labels the shapes, so ``--hypothesis-show-statistics`` shows how often a sequence nests,
closes a message by its end marker or leaves one truncated.
"""

from __future__ import annotations

from hypothesis import event, example, given
from hypothesis import strategies as st

from tlaup_parse import Framer, TlcMessage, Unframed, render_framed

START = "@!@!@STARTMSG {code}:{severity} @!@!@"
END = "@!@!@ENDMSG {code} @!@!@"

# Few codes, so that an end marker often matches an open start; 1000 nests in 1000 as in the captures.
codes = st.sampled_from(["1", "2", "1000"])
severities = st.sampled_from(["0", "1", "3", "4"])
# The last is one digit more than int() reads by default (4300): a line, not a marker, and nothing raises.
bad_codes = st.sampled_from(["-1", "01", "00", "x", "9" * 4301])
# Plain text may hold "\r" and "\n" anywhere, also at the end, so a fed line can end in "\n\n".
text = st.text(max_size=12)
some_text = st.text(min_size=1, max_size=4)
around = st.one_of(st.just(""), st.just(": "), st.just(","), text)


def start(before: str, code: str, severity: str) -> str:
    return before + START.format(code=code, severity=severity)


def end(code: str, after: str) -> str:
    return END.format(code=code) + after


starts = st.builds(start, around, codes, severities)
ends = st.builds(end, codes, around)
malformed = st.one_of(
    st.builds(start, st.just(""), bad_codes, severities),  # a negative code, a leading zero, letters, too long
    st.builds(end, bad_codes, st.just("")),
    st.builds(start, st.just(""), codes, bad_codes),  # a malformed severity
    st.builds(lambda code: f"@!@!@STARTMSG {code} @!@!@", codes),  # no severity
    st.builds(lambda line, after: line + after, starts, some_text),  # text after a start marker
    st.builds(lambda before, line: before + line, some_text, ends),  # text before an end marker
)
line = st.one_of(starts, ends, malformed, text)


def message(code: str, severity: str, before: str, body: list[list[str]], after: str) -> list[str]:
    return [start(before, code, severity), *[one for part in body for one in part], end(code, after)]


# A whole message, its start and its own end, with lines and whole messages nested in its body, so that a
# sequence often closes a message by its end marker and nests one in another (also of the same code).
blocks = st.recursive(
    st.lists(line, min_size=1, max_size=3),
    lambda inner: st.builds(message, codes, severities, around, st.lists(inner, max_size=4), around),
    max_leaves=25,
)
endings = st.sampled_from(["", "\n", "\r\n"])


@st.composite
def lines(draw: st.DrawFn) -> list[str]:
    """A sequence of whole messages, stray markers and plain text, each line with or without a line ending."""
    flat = [one for part in draw(st.lists(blocks, max_size=6)) for one in part]
    return [one + draw(endings) for one in flat]


def without_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return line[:-2]
    return line.removesuffix("\n")


def _label(items: list[Unframed | TlcMessage]) -> None:
    found = [item for item in items if isinstance(item, TlcMessage)]
    event(f"top-level messages: {len(found) if len(found) < 3 else '3 or more'}")
    stack = list(found)
    nested = closed = truncated = 0
    while stack:
        message = stack.pop()
        nested += len(message.nested)
        stack.extend(message.nested)
        if message.truncated:
            truncated += 1
        else:
            closed += 1
    event(f"nests: {nested > 0}")
    event(f"closed by its end marker: {closed > 0}")
    event(f"truncated: {truncated > 0}")


@given(lines())
# A marker line fed with two line endings: only one is removed, and the rest is not a marker (no "$" anchor).
@example(["x@!@!@STARTMSG 1:0 @!@!@\n\n"])
@example(["@!@!@STARTMSG 1:0 @!@!@\n", "@!@!@ENDMSG 1 @!@!@\n\n"])
def test_rendering_the_framed_lines_rebuilds_them(fed: list[str]) -> None:
    framer = Framer()
    items: list[Unframed | TlcMessage] = []
    for one in fed:
        items.extend(framer.feed(one))
    items.extend(framer.close())
    _label(items)
    assert [out for item in items for out in render_framed(item)] == [without_ending(one) for one in fed]
