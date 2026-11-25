"""``parse_value`` on each form, the roadmap's two defects, the golden value and the raw cases (design 10 P7).

The values here are single TLA+ values given to ``parse_value``, which 01 T12 rule 3 lets a test type. The one
multi-line value TLC wrapped, ``log`` in ``violation``, is read from the captures on both builds. Together these
are the test of preserved-behaviour row R28.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from tests.parse.drive import build_folders, read_lines
from tlaup_parse import Value, parse_value

if TYPE_CHECKING:
    from pathlib import Path

TLC_BUILDS = build_folders("tlc")
TLC_BUILD_IDS = [folder.name for folder in TLC_BUILDS]


# Expected trees. ``text`` is not compared, so it is left empty.
def i(n: int) -> Value:
    return Value(kind="int", text="", scalar=n)


def b(flag: bool) -> Value:
    return Value(kind="bool", text="", scalar=flag)


def s(string: str) -> Value:
    return Value(kind="string", text="", scalar=string)


def m(name: str) -> Value:
    return Value(kind="model", text="", scalar=name)


def set_(*items: Value) -> Value:
    return Value(kind="set", text="", items=items)


def seq(*items: Value) -> Value:
    return Value(kind="seq", text="", items=items)


def rec(**fields: Value) -> Value:
    return Value(kind="record", text="", fields=tuple(fields.items()))


def fun(*pairs: tuple[Value, Value]) -> Value:
    return Value(kind="function", text="", pairs=pairs)


def raw(text: str) -> Value:
    return Value(kind="raw", text=text, scalar=text)


@pytest.mark.parametrize(
    ("text", "tree"),
    [
        pytest.param("42", i(42), id="int"),
        pytest.param("-7", i(-7), id="negative-int"),
        pytest.param("TRUE", b(True), id="true"),
        pytest.param("FALSE", b(False), id="false"),
        pytest.param('"hello"', s("hello"), id="string"),
        pytest.param(r'"say \"hi\" \\ bye"', s('say "hi" \\ bye'), id="string-escaped-quotes"),
        pytest.param('"a :> b"', s("a :> b"), id="string-with-function-arrow"),
        pytest.param("m1", m("m1"), id="model"),
        pytest.param("1..3", Value(kind="interval", text="", bounds=(1, 3)), id="interval"),
        pytest.param("-2 .. -1", Value(kind="interval", text="", bounds=(-2, -1)), id="negative-interval"),
        pytest.param("{1, 2, 3}", set_(i(1), i(2), i(3)), id="set"),
        pytest.param('<<1, "a", TRUE>>', seq(i(1), s("a"), b(True)), id="seq"),
        pytest.param("{}", set_(), id="empty-set"),
        pytest.param("<< >>", seq(), id="empty-seq"),
        pytest.param('[a |-> 1, b |-> "x"]', rec(a=i(1), b=s("x")), id="record"),
        pytest.param(
            "{[x |-> 1], [x |-> 2]}",
            set_(rec(x=i(1)), rec(x=i(2))),
            id="set-of-records",
        ),
        pytest.param("(1 :> 2)", fun((i(1), i(2))), id="function"),
        pytest.param(
            "(<<1, a>> :> TRUE @@ <<2, b>> :> FALSE)",
            fun((seq(i(1), m("a")), b(True)), (seq(i(2), m("b")), b(False))),
            id="function-tuple-keys",
        ),
        pytest.param(
            '[r |-> {<<1, (k :> [v |-> {"s"}])>>}, n |-> 0..2]',
            rec(
                r=set_(seq(i(1), fun((m("k"), rec(v=set_(s("s"))))))),
                n=Value(kind="interval", text="", bounds=(0, 2)),
            ),
            id="nested",
        ),
    ],
)
def test_each_form(text: str, tree: Value) -> None:
    assert parse_value(text) == tree


def test_root_text_is_the_input() -> None:
    text = "  {1, 2}\n"
    assert parse_value(text).text == text


def test_node_text_is_its_source_span() -> None:
    value = parse_value("[a |-> {1,  2}, b |-> << >>]")
    assert value.fields[0][1].text == "{1,  2}"
    assert value.fields[1][1].text == "<< >>"


def test_function_is_not_its_first_key() -> None:
    """Roadmap defect: ``(a :> 1 @@ b :> 2)`` parsed to ``a``."""
    assert parse_value("(a :> 1 @@ b :> 2)") == fun((m("a"), i(1)), (m("b"), i(2)))


def test_wrapped_value_parses_as_on_one_line() -> None:
    """Roadmap defect: a value TLC wraps over several lines always fell back to raw text."""
    one_line = '<<[op |-> "add", key |-> "alpha"], [op |-> "del", key |-> "beta"]>>'
    wrapped = '<< [ op |-> "add",\n     key |-> "alpha" ],\n   [ op |-> "del",\n     key |->\n         "beta" ] >>'
    parsed = parse_value(wrapped)
    assert parsed.kind == "seq"
    assert parsed == parse_value(one_line)


def log_of_last_state(path: Path) -> str:
    """The text of ``log`` in the last state of the file, cut out as package 13's trace parser would.

    From the last line starting ``/\\ log = `` to the line before the next ``/\\ `` line or the blank line that
    ends the state, with the prefix removed and the line endings kept.
    """
    lines = read_lines(path)
    prefix = "/\\ log = "
    start = max(index for index, line in enumerate(lines) if line.startswith(prefix))
    end = start + 1
    while end < len(lines) and lines[end].strip() and not lines[end].startswith("/\\ "):
        end += 1
    return "".join(lines[start:end]).removeprefix(prefix).rstrip("\n")


@pytest.mark.parametrize("folder", TLC_BUILDS, ids=TLC_BUILD_IDS)
def test_golden_wrapped_sequence_of_records(folder: Path) -> None:
    text = log_of_last_state(folder / "violation.out")
    assert "\n" in text  # TLC wrapped it
    value = parse_value(text)
    assert value.kind == "seq"
    assert value.text == text
    note = s("a deliberately long note to force the value to wrap across several lines")
    entry = rec(op=s("add"), key=s("alpha"), val=i(1), note=note)
    assert value.items == (entry, entry, entry)


@pytest.mark.parametrize(
    "text",
    [
        pytest.param("[S -> T]", id="function-set"),
        pytest.param("SUBSET S", id="subset"),
        pytest.param("{x \\in S : x > 1}", id="set-comprehension"),
        pytest.param("{1, 2", id="unbalanced"),
        pytest.param("", id="empty"),
        pytest.param("1 2", id="text-after-value"),
        pytest.param("<<1>> >>", id="text-after-seq"),
        pytest.param("[]", id="empty-record"),
        pytest.param("- 1", id="minus-apart"),
        pytest.param('"open', id="unterminated-string"),
        pytest.param('"open\\', id="string-ending-in-backslash"),
    ],
)
def test_raw(text: str) -> None:
    value = parse_value(text)
    assert value == raw(text)
    assert value.text == text
    assert value.scalar == text


def test_two_raw_values_with_different_text_differ() -> None:
    assert parse_value("SUBSET S") != parse_value("SUBSET T")


def test_failure_deep_inside_gives_a_raw_root() -> None:
    text = "[a |-> {<<1, (k :> [S -> T])>>}]"
    assert parse_value(text) == raw(text)


def test_nesting_deeper_than_the_recursion_limit_is_raw() -> None:
    depth = sys.getrecursionlimit() + 100
    text = "<<" * depth + "1" + ">>" * depth
    assert parse_value(text) == raw(text)
