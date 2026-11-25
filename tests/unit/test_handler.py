"""The root group's handler, in-process (design 14 F10, 02 X1): small apps built with `cls=TlaupGroup`.

No hidden test command is added to tlaup; tlaup's own `app` is called only for the error before the context
exists (a relative TLAUP_HOME through the old `tools dir`, which 29a renames) and for the no-command cases.
"""

import errno
import importlib.metadata
import os
from collections.abc import Callable, Iterator

import pytest
import typer
from typer.testing import CliRunner, Result

from tlaup import context
from tlaup.cli import TlaupGroup, report
from tlaup.cli import app as tlaup_app
from tlaup.errors import CannotAsk, ConfigInvalid, ModuleNotFound, TlaupError

INTERNAL_HINT = 'hint: run it again as "tlaup --debug ..." or with TLAUP_DEBUG=1, and report it at '


@pytest.fixture(autouse=True)
def _fresh_context() -> Iterator[None]:
    context.reset()
    yield
    context.reset()


def small_app(cls: type[TlaupGroup] = TlaupGroup) -> typer.Typer:
    app = typer.Typer(cls=cls, name="small", add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)

    @app.callback()
    def root(debug: bool = typer.Option(False, "--debug")) -> None:
        """A root with tlaup's --debug, so the handler can read it from the context."""

    return app


def app_raising(error: BaseException | Callable[[], BaseException], cls: type[TlaupGroup] = TlaupGroup) -> typer.Typer:
    app = small_app(cls)

    @app.command()
    def fail() -> None:
        raise error() if callable(error) else error

    return app


def invoke(app: typer.Typer, *args: str) -> Result:
    return CliRunner().invoke(app, list(args))


def lines(text: str) -> list[str]:
    return text.splitlines()


# --- what a command raises ---


def test_an_internal_error_is_one_line_and_5() -> None:
    result = invoke(app_raising(RuntimeError("boom")), "fail")
    assert result.exit_code == 5
    assert result.stdout == ""
    assert lines(result.stderr)[0] == "error: internal error: RuntimeError: boom"
    assert lines(result.stderr)[1].startswith(INTERNAL_HINT)
    assert len(lines(result.stderr)) == 2
    assert "Traceback" not in result.stderr


def test_the_internal_error_hint_names_the_issues_address_from_the_metadata() -> None:
    urls = importlib.metadata.metadata("tlaup").get_all("Project-URL") or []
    issues = next(entry.split(",", 1)[1].strip() for entry in urls if entry.split(",", 1)[0] == "Issues")
    result = invoke(app_raising(RuntimeError("boom")), "fail")
    assert lines(result.stderr)[1] == INTERNAL_HINT + issues


def test_end_of_input_is_cannot_ask() -> None:
    result = invoke(app_raising(EOFError()), "fail")
    assert result.exit_code == CannotAsk.exit_code == 3
    assert lines(result.stderr) == ["error: the input ended while tlaup was waiting for an answer"]


def test_a_domain_error_from_a_nested_subgroup() -> None:
    app = small_app()
    outer = typer.Typer()
    inner = typer.Typer()
    app.add_typer(outer, name="outer")
    outer.add_typer(inner, name="inner")

    @inner.command()
    def deep() -> None:
        raise ModuleNotFound("no module Foo", hint="run tlaup module list", details="looked in a\nlooked in b")  # noqa: TRY003

    result = invoke(app, "outer", "inner", "deep")
    assert result.exit_code == 4
    assert result.stdout == ""
    assert lines(result.stderr) == [
        "error: no module Foo",
        "hint: run tlaup module list",
        "  looked in a",
        "  looked in b",
    ]


@pytest.mark.parametrize("error", [KeyboardInterrupt, typer.Abort], ids=["KeyboardInterrupt", "Abort"])
def test_an_interrupt_is_130(error: Callable[[], BaseException]) -> None:
    assert invoke(app_raising(error), "fail").exit_code == 130


def test_typer_usage_errors_are_2_in_typers_form() -> None:
    app = small_app()

    @app.command()
    def needs(name: str) -> None:
        pass  # pragma: no cover - never reached

    @app.command()
    def bad() -> None:
        raise typer.BadParameter("not a good value")  # noqa: TRY003

    cases = {
        "missing argument": ["needs"],
        "unknown command": ["nosuch"],
        "unknown option": ["needs", "x", "--nosuch"],
        "bad parameter": ["bad"],
    }
    for name, args in cases.items():
        result = invoke(app, *args)
        assert result.exit_code == 2, name
        assert result.stdout == "", name
        assert "Usage:" in result.stderr, name
        assert "error:" not in result.stderr, name


def test_a_command_that_raises_typer_exit_keeps_its_code() -> None:
    assert invoke(app_raising(typer.Exit(1)), "fail").exit_code == 1


# --- the root's options: the make_context wrapper ---


def app_with_eager(error: BaseException) -> typer.Typer:
    def eager(value: bool) -> None:
        if value:
            raise error

    app = typer.Typer(cls=TlaupGroup, add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)

    @app.callback()
    def root(_: bool = typer.Option(False, "--boom", callback=eager, is_eager=True)) -> None:
        """A root with an eager option."""

    @app.command()
    def cmd() -> None:
        pass  # pragma: no cover - never reached

    return app


def test_an_eager_option_raising_an_internal_error() -> None:
    result = invoke(app_with_eager(RuntimeError("eager")), "--boom", "cmd")
    assert result.exit_code == 5
    assert lines(result.stderr)[0] == "error: internal error: RuntimeError: eager"


def test_an_eager_option_raising_a_domain_error() -> None:
    result = invoke(app_with_eager(ConfigInvalid("bad config")), "--boom", "cmd")
    assert result.exit_code == 3
    assert lines(result.stderr) == ["error: bad config"]


def test_an_eager_option_raising_a_broken_pipe() -> None:
    result = invoke(app_with_eager(BrokenPipeError()), "--boom", "cmd")
    assert result.exit_code == 141
    assert result.stderr == ""


# --- notes ---


def test_report_prints_message_hint_details_then_notes(capsys: pytest.CaptureFixture[str]) -> None:
    error = ModuleNotFound("no module Foo", hint="run tlaup module list", details="looked in a")
    error.add_note("first note")
    error.add_note("second note")
    report(error, None, ())
    captured = capsys.readouterr()
    assert captured.out == ""
    assert lines(captured.err) == [
        "error: no module Foo",
        "hint: run tlaup module list",
        "  looked in a",
        "first note",
        "second note",
    ]


def test_a_closed_pipe_prints_its_note_alone() -> None:
    def broken() -> BaseException:
        error = BrokenPipeError()
        error.add_note("Checkpoint kept: somewhere")
        return error

    result = invoke(app_raising(broken), "fail")
    assert result.exit_code == 141
    assert result.stdout == ""
    assert result.stderr == "Checkpoint kept: somewhere\n"


def test_an_internal_error_prints_its_notes_after_the_hint() -> None:
    def noted() -> BaseException:
        error = RuntimeError("boom")
        error.add_note("a note")
        return error

    result = invoke(app_raising(noted), "fail")
    assert lines(result.stderr)[0] == "error: internal error: RuntimeError: boom"
    assert lines(result.stderr)[1].startswith(INTERNAL_HINT)
    assert lines(result.stderr)[2:] == ["a note"]


# --- debug ---


@pytest.mark.parametrize(
    ("error", "first_line"),
    [
        (ConfigInvalid("bad config"), "error: bad config"),
        (RuntimeError("boom"), "error: internal error: RuntimeError: boom"),
    ],
    ids=["domain", "internal"],
)
@pytest.mark.parametrize("how", ["--debug", "TLAUP_DEBUG=1"])
def test_debug_prints_the_line_then_a_traceback(
    error: TlaupError | RuntimeError, first_line: str, how: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    args = ["fail"]
    if how == "--debug":
        args.insert(0, "--debug")
    else:
        monkeypatch.setenv("TLAUP_DEBUG", "1")
    result = invoke(app_raising(error), *args)
    assert result.exit_code == (5 if isinstance(error, RuntimeError) else 3)
    assert lines(result.stderr)[0] == first_line
    assert "Traceback (most recent call last):" in result.stderr
    assert result.stderr.index("Traceback") > result.stderr.index(first_line)


def test_debug_in_make_context_is_read_from_the_arguments() -> None:
    def eager(value: bool) -> None:
        if value:
            raise RuntimeError("eager")

    app = typer.Typer(cls=TlaupGroup, add_completion=False, no_args_is_help=True, pretty_exceptions_enable=False)

    @app.callback()
    def root(
        debug: bool = typer.Option(False, "--debug"),
        _: bool = typer.Option(False, "--boom", callback=eager, is_eager=True),
    ) -> None:
        """No context exists while an eager option runs."""

    @app.command()
    def cmd() -> None:
        pass  # pragma: no cover - never reached

    assert "Traceback" in invoke(app, "--debug", "--boom", "cmd").stderr
    assert "Traceback" not in invoke(app, "--boom", "cmd").stderr


def test_debug_after_the_subcommand_is_a_usage_error() -> None:
    result = invoke(app_raising(RuntimeError("boom")), "fail", "--debug")
    assert result.exit_code == 2
    assert result.stdout == ""


# --- tlaup's own app ---


@pytest.mark.parametrize("debug", [False, True])
def test_an_error_before_the_context_exists(debug: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TLAUP_HOME", "relative/path")
    context.reset()
    args = ["--debug", "tools", "dir"] if debug else ["tools", "dir"]  # 29a changes it to `tool dir`
    result = invoke(tlaup_app, *args)
    assert result.exit_code == 3
    assert result.stdout == ""
    errors = [line for line in lines(result.stderr) if line.startswith("error:")]
    assert len(errors) == 1
    assert "TLAUP_HOME" in errors[0]
    assert ("Traceback" in result.stderr) is debug


@pytest.mark.parametrize("args", [[], ["config"]], ids=["tlaup", "tlaup config"])
def test_no_command_prints_help_on_stdout_and_exits_2(args: list[str]) -> None:
    result = invoke(tlaup_app, *args)
    assert result.exit_code == 2
    assert "Usage:" in result.stdout
    assert result.stderr == ""


def test_the_root_callback_puts_the_context_on_ctx_obj(monkeypatch: pytest.MonkeyPatch) -> None:
    result = invoke(tlaup_app, "--debug", "tools", "dir")
    assert result.exit_code == 0
    built = context.get_context()
    assert built.debug is True
    assert result.stdout.strip() == str(built.paths.cache / "tools")


# --- writes that fail ---


class WindowsPipe(TlaupGroup):
    """Answers "Windows, and a standard stream is a pipe" (D57); a subclass in the test, not a patch."""

    @staticmethod
    def closed_pipe(e: OSError) -> bool:
        return e.errno == errno.EINVAL and e.filename is None


def _einval() -> OSError:
    return OSError(errno.EINVAL, "Invalid argument")


def test_einval_on_a_windows_pipe_is_a_closed_pipe() -> None:
    result = invoke(app_raising(_einval, cls=WindowsPipe), "fail")
    assert result.exit_code == 141
    assert result.stdout == ""
    assert result.stderr == ""


@pytest.mark.skipif(os.name == "nt", reason="tlaup's own rule is the Windows one there")
def test_einval_elsewhere_is_an_internal_error() -> None:
    result = invoke(app_raising(_einval), "fail")
    assert result.exit_code == 5
    assert lines(result.stderr)[0].startswith("error: internal error: OSError: ")


def test_a_full_disk_is_cannot_write_output() -> None:
    result = invoke(app_raising(lambda: OSError(errno.ENOSPC, "No space left on device")), "fail")
    assert result.exit_code == 5
    assert lines(result.stderr) == ["error: cannot write output: No space left on device"]


def test_a_full_disk_with_a_file_name_is_an_internal_error() -> None:
    result = invoke(app_raising(lambda: OSError(errno.ENOSPC, "No space left on device", "some-file")), "fail")
    assert result.exit_code == 5
    assert lines(result.stderr)[0].startswith("error: internal error: OSError: ")
