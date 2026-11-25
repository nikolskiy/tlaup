"""The messages helper (design 14 F6): every `Ui` is built on in-memory streams through its constructor."""

import io
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from tests.expected import assert_matches
from tlaup.errors import CannotAsk
from tlaup.ui import Ui, _PipeConsole

EXPECTED = Path(__file__).parent / "expected" / "ui"
ESC = "\x1b"


@contextmanager
def process_streams(**streams: Any) -> Iterator[None]:
    """Put streams in `sys` for a moment, as `CliRunner` does (monkeypatch is for the environment only)."""
    saved = {name: getattr(sys, name) for name in streams}
    for name, stream in streams.items():
        setattr(sys, name, stream)
    try:
        yield
    finally:
        for name, stream in saved.items():
            setattr(sys, name, stream)


def make(stdin: str = "", **kwargs: Any) -> tuple[Ui, io.StringIO, io.StringIO]:
    out, err = io.StringIO(), io.StringIO()
    options: dict[str, Any] = {"color": False, "env": {}}
    options.update(kwargs)
    return Ui(out, err, io.StringIO(stdin), **options), out, err


KINDS: dict[str, Callable[[Ui], None]] = {
    "error": lambda ui: ui.error("no version pinned"),
    "error-hint": lambda ui: ui.error("no version pinned", hint="run `tlaup tool pin v1.7.4`"),
    "error-details": lambda ui: ui.error("cannot read it", details="first line\nsecond line"),
    "warning": lambda ui: ui.warning('config.yaml: unknown key "workspace" (ignored)'),
    "note": lambda ui: ui.note("Pinned v1.7.4@5a47802"),
    "result": lambda ui: ui.result("/cache/tools/v1.7.4"),
}
STDOUT_KINDS = {"result"}


def render(kind: str, **kwargs: Any) -> tuple[str, str]:
    ui, out, err = make(**kwargs)
    KINDS[kind](ui)
    return out.getvalue(), err.getvalue()


@pytest.mark.parametrize("kind", KINDS)
def test_plain_messages(kind: str, request: pytest.FixtureRequest) -> None:
    out, err = render(kind)
    text, other = (out, err) if kind in STDOUT_KINDS else (err, out)
    assert other == ""
    assert ESC not in text
    assert_matches(text, EXPECTED / f"{kind}.plain.txt", request)


@pytest.mark.parametrize("kind", KINDS)
def test_colored_messages(kind: str, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    out, err = render(kind, color=True, terminal=True)
    text, other = (out, err) if kind in STDOUT_KINDS else (err, out)
    assert other == ""
    assert_matches(text, EXPECTED / f"{kind}.color.txt", request)


@pytest.mark.parametrize("kind", KINDS)
def test_no_color_variable_means_no_escape_at_all(kind: str) -> None:
    out, err = render(kind, color=None, terminal=True, env={"NO_COLOR": "1"})
    assert ESC not in out + err
    assert (out + err).strip()


def test_policy_none_colours_a_terminal_without_the_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    _, err = render("error", color=None, terminal=True)
    assert ESC in err
    _, err = render("error", color=None, terminal=False)
    assert ESC not in err


def test_text_from_outside_is_not_markup() -> None:
    ui, _, err = make()
    ui.error("[red]x[/red] [bold]", hint="[link=x]y[/link]", details=":smile: [b]z")
    assert err.getvalue() == "error: [red]x[/red] [bold]\nhint: [link=x]y[/link]\n  :smile: [b]z\n"
    ui, out, _ = make()
    ui.result("[red]x[/red] :smile: 123")
    assert out.getvalue() == "[red]x[/red] :smile: 123\n"


def test_a_long_message_stays_on_one_line() -> None:
    long = "/very/long/path/" + "x" * 300
    ui, out, err = make(size=(40, 20))
    ui.error(long)
    ui.warning(long)
    ui.note(long)
    ui.result(long)
    assert err.getvalue().splitlines() == [f"error: {long}", f"warning: {long}", long]
    assert out.getvalue() == long + "\n"


def test_ask_returns_a_valid_answer() -> None:
    ui, out, err = make("v1.7.4\n")
    assert ui.ask("Which build?", choices=["rolling", "v1.7.4"], default="rolling") == "v1.7.4"
    assert err.getvalue() == "Which build? [rolling] "
    assert out.getvalue() == ""


def test_ask_again_after_an_invalid_answer() -> None:
    ui, out, err = make("maybe\n  rolling \n")
    assert ui.ask("Which?", choices=["rolling", "v1.7.4"], default=None) == "rolling"
    assert err.getvalue().count("Which?") == 2
    assert out.getvalue() == ""


def test_ask_newline_gives_the_default() -> None:
    ui, _, _ = make("\n")
    assert ui.ask("Which?", choices=["a", "b"], default="b") == "b"


def test_ask_newline_without_default_asks_again() -> None:
    ui, _, err = make("\na\n")
    assert ui.ask("Which?", choices=["a", "b"], default=None) == "a"
    assert err.getvalue().count("Which?") == 2


def test_ask_at_end_of_input_is_cannot_ask() -> None:
    ui, out, err = make("")
    with pytest.raises(CannotAsk) as raised:
        ui.ask("Which?", choices=["a"], default="a")
    assert raised.value.exit_code == 3
    assert "Which?" in err.getvalue()
    assert out.getvalue() == ""


def test_ask_does_not_catch_the_interrupt() -> None:
    class Interrupted(io.StringIO):
        def readline(self, size: int = -1, /) -> str:  # noqa: ARG002
            raise KeyboardInterrupt

    ui = Ui(io.StringIO(), io.StringIO(), Interrupted(), color=False, env={})
    with pytest.raises(KeyboardInterrupt):
        ui.ask("Which?", choices=["a"], default="a")


def test_is_interactive_follows_the_argument_or_the_streams() -> None:
    assert make()[0].is_interactive() is False
    assert make(interactive=True)[0].is_interactive() is True
    assert make(interactive=False)[0].is_interactive() is False


def test_is_interactive_needs_stdin_and_stderr_to_be_terminals() -> None:
    class Terminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    assert Ui(io.StringIO(), Terminal(), Terminal(), color=None, env={}).is_interactive() is True
    assert Ui(io.StringIO(), Terminal(), io.StringIO(), color=None, env={}).is_interactive() is False
    assert Ui(io.StringIO(), io.StringIO(), Terminal(), color=None, env={}).is_interactive() is False


def test_a_broken_pipe_gets_out_as_itself() -> None:
    class Closed(io.StringIO):
        def write(self, s: str, /) -> int:  # noqa: ARG002
            raise BrokenPipeError

    ui = Ui(Closed(), io.StringIO(), io.StringIO(), color=False, env={})
    assert isinstance(ui.out, _PipeConsole)
    assert isinstance(ui.err, _PipeConsole)
    with pytest.raises(BrokenPipeError):
        ui.result("x")


def test_for_process_uses_the_current_streams(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TERM", "dumb")
    out, err, stdin = io.StringIO(), io.StringIO(), io.StringIO("a\n")
    with process_streams(stdout=out, stderr=err, stdin=stdin):
        ui = Ui.for_process()
    ui.result("r")
    ui.note("n")
    assert ui.ask("Q?", choices=["a"], default=None) == "a"
    assert out.getvalue() == "r\n"
    assert err.getvalue().startswith("n\nQ?")
    assert ui.is_interactive() is False


def test_for_process_replaces_what_the_encoding_lacks(monkeypatch: pytest.MonkeyPatch) -> None:
    raw, raw_err = io.BytesIO(), io.BytesIO()
    out = io.TextIOWrapper(raw, encoding="ascii", write_through=True)
    err = io.TextIOWrapper(raw_err, encoding="ascii", write_through=True)
    with process_streams(stdout=out, stderr=err):
        ui = Ui.for_process()
    ui.result("café")
    ui.note("café")
    assert raw.getvalue() == b"caf?\n"
    assert raw_err.getvalue() == b"caf?\n"


def test_ask_shows_only_the_default_and_never_the_choices() -> None:
    ui, _, err = make("a\n")
    ui.ask("Which?", choices=["a", "b"], default=None)
    assert err.getvalue() == "Which? "


@pytest.mark.parametrize(
    ("question", "default", "shown"),
    [
        ("Choice", "1", "Choice [1]: "),
        ("Choice", None, "Choice: "),
        ("Which build should be pinned?", None, "Which build should be pinned? "),
        ("Which build should be pinned?", "1", "Which build should be pinned? [1] "),
        ("Which build:", None, "Which build: "),
    ],
)
def test_ask_adds_a_colon_only_when_the_question_does_not_end_in_one_or_a_question_mark(
    question: str, default: str | None, shown: str
) -> None:
    ui, _, err = make("1\n")
    ui.ask(question, choices=["1"], default=default)
    assert err.getvalue() == shown
