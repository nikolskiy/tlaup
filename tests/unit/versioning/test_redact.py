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
    first = result.stderr.splitlines()[0]
    assert first.startswith("error: internal error: RuntimeError: token ***")
    assert "Traceback (most recent call last):" in result.stderr
    assert result.stderr.count("***") >= 2  # the error line and the traceback's last line
    assert GH not in result.stderr
    assert "secret" not in result.stderr


def test_importing_redact_does_not_load_the_client() -> None:
    # Only the client: tlaup.versioning's __init__ still loads requests until package 29b empties it.
    code = "import sys, tlaup.versioning.redact; print('tlaup.versioning.github' in sys.modules)"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "False"
