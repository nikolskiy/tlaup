"""The four value properties of design 01 T7: round trip, white space does not matter, total, never partial.

The strategy builds a ``Value`` tree and ``tokens`` writes it in TLC's notation, one token per item. The printer
is a second reading of TLC's notation by the same hands (T7, Risks); the golden value in ``test_values.py`` is
the check from outside. ``event`` labels the root's kind and the tree's depth, so ``--hypothesis-show-statistics``
shows how often a deep or odd value comes up.
"""

from __future__ import annotations

from hypothesis import event, given
from hypothesis import strategies as st

from tlaup_parse import Value, parse_value

MAX_DEPTH = 4

names = st.from_regex(r"[A-Za-z_][A-Za-z0-9_]{0,5}", fullmatch=True)
model_names = names.filter(lambda name: name not in {"TRUE", "FALSE"})
small_ints = st.integers(min_value=-(10**12), max_value=10**12)
# Quotes and backslashes often, so that escapes are exercised; any other character too.
string_chars = st.one_of(st.sampled_from(['"', "\\", ":", ">", "@", " "]), st.characters(codec="utf-8"))

ints = st.builds(lambda n: Value(kind="int", text="", scalar=n), small_ints)
bools = st.builds(lambda flag: Value(kind="bool", text="", scalar=flag), st.booleans())
strings = st.builds(lambda text: Value(kind="string", text="", scalar=text), st.text(string_chars, max_size=8))
models = st.builds(lambda name: Value(kind="model", text="", scalar=name), model_names)
intervals = st.builds(lambda a, b: Value(kind="interval", text="", bounds=(a, b)), small_ints, small_ints)
leaves = st.one_of(ints, bools, strings, models, intervals)
non_string_leaves = st.one_of(ints, bools, models, intervals)


def collections(children: st.SearchStrategy[Value]) -> st.SearchStrategy[Value]:
    """One level of sets, sequences, records and functions over ``children``."""
    some = st.lists(children, max_size=4).map(tuple)
    keys = st.one_of(non_string_leaves, st.lists(non_string_leaves, max_size=3).map(_seq_of))
    return st.one_of(
        some.map(lambda items: Value(kind="set", text="", items=items)),
        some.map(lambda items: Value(kind="seq", text="", items=items)),
        st.lists(st.tuples(names, children), min_size=1, max_size=4).map(
            lambda fields: Value(kind="record", text="", fields=tuple(fields))
        ),
        st.lists(st.tuples(keys, children), min_size=1, max_size=4).map(
            lambda pairs: Value(kind="function", text="", pairs=tuple(pairs))
        ),
    )


def _seq_of(items: list[Value]) -> Value:
    return Value(kind="seq", text="", items=tuple(items))


def nested(depth: int) -> st.SearchStrategy[Value]:
    """Values nested at most ``depth`` levels; each level may also stop at a leaf."""
    if depth == 0:
        return leaves
    return st.one_of(leaves, collections(nested(depth - 1)))


values = nested(MAX_DEPTH)


def depth_of(value: Value) -> int:
    children = [*value.items, *(child for _, child in value.fields)]
    children += [part for pair in value.pairs for part in pair]
    return 1 + max((depth_of(child) for child in children), default=0)


def _escaped(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _listed(items: list[list[str]]) -> list[str]:
    out: list[str] = []
    for index, item in enumerate(items):
        if index:
            out.append(",")
        out.extend(item)
    return out


def tokens(value: Value) -> list[str]:  # noqa: PLR0911
    """The value in TLC's notation, as a list of tokens."""
    if value.kind in {"int", "model"}:
        return [str(value.scalar)]
    if value.kind == "bool":
        return ["TRUE" if value.scalar else "FALSE"]
    if value.kind == "string":
        assert isinstance(value.scalar, str)
        return [_escaped(value.scalar)]
    if value.kind == "interval":
        assert value.bounds is not None
        return [str(value.bounds[0]), "..", str(value.bounds[1])]
    if value.kind == "set":
        return ["{", *_listed([tokens(item) for item in value.items]), "}"]
    if value.kind == "seq":
        return ["<<", *_listed([tokens(item) for item in value.items]), ">>"]
    if value.kind == "record":
        return ["[", *_listed([[name, "|->", *tokens(child)] for name, child in value.fields]), "]"]
    assert value.kind == "function"
    out = ["("]
    for index, (key, child) in enumerate(value.pairs):
        if index:
            out.append("@@")
        out.extend([*tokens(key), ":>", *tokens(child)])
    return [*out, ")"]


def printed(value: Value) -> str:
    return " ".join(tokens(value))


def label(value: Value) -> None:
    event(f"root kind: {value.kind}")
    event(f"depth: {depth_of(value)}")


@given(values)
def test_round_trip(value: Value) -> None:
    label(value)
    assert parse_value(printed(value)) == value


# White space TLC's wrapping might put between two tokens: a space, newlines, indentation.
gaps = st.sampled_from([" ", "\n", "\n   ", "\n\t", "  \n     ", "\r\n  "])


@given(values, st.data())
def test_white_space_does_not_matter(value: Value, data: st.DataObject) -> None:
    label(value)
    parts = tokens(value)
    # One gap before each token and one after the last; the ends may also have none.
    ends = st.one_of(st.just(""), gaps)
    inner = data.draw(st.lists(gaps, min_size=len(parts) - 1, max_size=len(parts) - 1))
    text = data.draw(ends) + "".join(part + gap for part, gap in zip(parts, [*inner, ""], strict=True))
    text += data.draw(ends)
    parsed = parse_value(text)
    assert parsed == value
    assert parsed.text == text


@given(st.text())
def test_total(text: str) -> None:
    result = parse_value(text)
    assert result.text == text


def raw_nodes(value: Value) -> int:
    children = [*value.items, *(child for _, child in value.fields)]
    children += [part for pair in value.pairs for part in pair]
    return (value.kind == "raw") + sum(raw_nodes(child) for child in children)


# Any text, and printed values with a few characters cut out, so that many inputs fail deep inside a tree.
broken = st.builds(
    lambda text, start, length: text[:start] + text[start + length :],
    values.map(printed),
    st.integers(min_value=0, max_value=40),
    st.integers(min_value=1, max_value=3),
)


@given(st.one_of(st.text(), broken))
def test_never_a_partial_tree(text: str) -> None:
    result = parse_value(text)
    event(f"result kind: {result.kind}")
    if result.kind == "raw":
        assert result == Value(kind="raw", text=text, scalar=text)
        assert raw_nodes(result) == 1
    else:
        assert raw_nodes(result) == 0
