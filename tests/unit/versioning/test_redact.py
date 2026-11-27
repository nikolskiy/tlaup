"""The debug filter (design 12 V7), alone and through the root handler (14 F10)."""

import subprocess
import sys

import pytest
import typer
from typer.testing import CliRunner

from tlaup import context
from tlaup.cli import TlaupGroup
from tlaup.versioning.redact import redact

GH = "gh-value-not-a-secret-1"
GITHUB = "github-value-not-a-secret-2"


def test_both_tokens_become_stars() -> None:
    text = f"first {GH} then {GITHUB}, and {GH} again"
    assert redact(text, {"GH_TOKEN": GH, "GITHUB_TOKEN": GITHUB}) == "first *** then ***, and *** again"


def test_an_address_loses_its_query_string_and_the_rest_of_the_line_stays() -> None:
    text = "GET https://example.org/a/b?sig=x&page=2 failed\nnext 'http://h.example/p?q=1' line"
    assert redact(text, {}) == "GET https://example.org/a/b failed\nnext 'http://h.example/p' line"


def test_a_token_that_holds_the_other_is_replaced_whole() -> None:
    assert redact("abcdef and abc", {"GH_TOKEN": "abc", "GITHUB_TOKEN": "abcdef"}) == "*** and ***"
    assert redact("abcdef and abc", {"GH_TOKEN": "abcdef", "GITHUB_TOKEN": "abc"}) == "*** and ***"


def test_an_empty_variable_replaces_nothing() -> None:
    text = "a text with no secret in it, and a = sign"
    assert redact(text, {"GH_TOKEN": "", "GITHUB_TOKEN": ""}) == text


def test_a_text_with_neither_token_nor_address_is_unchanged() -> None:
    text = "nothing here? no: just a question mark"
    assert redact(text, {"GH_TOKEN": GH, "GITHUB_TOKEN": GITHUB}) == text


def test_the_handler_filters_the_error_line_and_the_traceback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", GH)
    message = f"token {GH} at https://example.org/x?sig=secret"
    app = typer.Typer(cls=TlaupGroup, name="small", add_completion=False, pretty_exceptions_enable=False)

    @app.callback()
    def root(debug: bool = typer.Option(False, "--debug")) -> None:
        """A root with tlaup's --debug."""

    @app.command()
    def fail() -> None:
        raise RuntimeError(message)

    context.reset()
    try:
        result = CliRunner().invoke(app, ["--debug", "fail"])
    finally:
        context.reset()
    assert result.exit_code == 5
    out = result.stderr.splitlines()
    assert out[0] == "error: internal error: RuntimeError: token *** at https://example.org/x"
    assert "Traceback (most recent call last):" in result.stderr
    assert "RuntimeError: token *** at https://example.org/x" in out[out.index("Traceback (most recent call last):") :]
    assert GH not in result.stderr
    assert "secret" not in result.stderr


def test_importing_redact_loads_neither_the_client_nor_requests() -> None:
    code = (
        "import sys, tlaup.versioning.redact\n"
        "print('tlaup.versioning.github' in sys.modules, 'requests' in sys.modules)"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "False False"
