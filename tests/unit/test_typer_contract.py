"""The public names of Typer that tlaup relies on (design 14 F10, contract tests, public half).

Each check names the Typer name it is about, so an upgrade that renames or reshapes one says which.
The private half, for completion, is added by package 47.
"""

import inspect

import pytest
import typer
import typer.core
import typer.main


@pytest.mark.parametrize("name", ["Exit", "Abort", "BadParameter", "TyperException"])
def test_public_exception_exists(name: str) -> None:
    assert isinstance(getattr(typer, name, None), type), f"typer.{name} is missing"


def test_bad_parameter_is_a_typer_exception() -> None:
    assert issubclass(typer.BadParameter, typer.TyperException), "typer.BadParameter is not a typer.TyperException"


def test_abort_is_not_a_typer_exception() -> None:
    # mapped() lets every TyperException through before its typer.Abort branch; that branch would be dead.
    assert not issubclass(typer.Abort, typer.TyperException), "typer.Abort became a typer.TyperException"


def test_exit_is_not_a_typer_exception() -> None:
    assert not issubclass(typer.Exit, typer.TyperException), "typer.Exit became a typer.TyperException"


def test_an_unknown_option_raises_a_typer_exception() -> None:
    app = typer.Typer(add_completion=False)

    @app.command()
    def only() -> None:
        pass  # pragma: no cover - never reached

    command = typer.main.get_command(app)
    with pytest.raises(typer.TyperException):
        command.main(["--nosuch"], standalone_mode=False)


def test_typer_group_make_context_signature() -> None:
    parameters = list(inspect.signature(typer.core.TyperGroup.make_context).parameters.values())
    shape = [(p.name, p.kind, p.default) for p in parameters]
    empty = inspect.Parameter.empty
    assert shape == [
        ("self", inspect.Parameter.POSITIONAL_OR_KEYWORD, empty),
        ("info_name", inspect.Parameter.POSITIONAL_OR_KEYWORD, empty),
        ("args", inspect.Parameter.POSITIONAL_OR_KEYWORD, empty),
        ("parent", inspect.Parameter.POSITIONAL_OR_KEYWORD, None),
        ("extra", inspect.Parameter.VAR_KEYWORD, empty),
    ], f"typer.core.TyperGroup.make_context changed shape: {shape}"


def test_typer_group_invoke_signature() -> None:
    names = list(inspect.signature(typer.core.TyperGroup.invoke).parameters)
    assert names == ["self", "ctx"], f"typer.core.TyperGroup.invoke changed shape: {names}"
