"""The public names of Typer that tlaup relies on (design 14 F10, contract tests, public half).

Each check names the Typer name it is about, so an upgrade that renames or reshapes one says which.
The private half, for completion (package 47), is at the end.
"""

import inspect
from typing import Any

import pytest
import typer
import typer.core
import typer.main
from typer import _completion_classes, _completion_shared
from typer._click import shell_completion


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


# The private half: the two modules tlaup/cmd/completion.py is built on (design 23 C3, 14 F10).


def _script(shell: str) -> str:
    return _completion_shared.get_completion_script(prog_name="tlaup", complete_var="_TLAUP_COMPLETE", shell=shell)


def test_completion_init_takes_no_argument() -> None:
    assert not [
        p
        for p in inspect.signature(_completion_classes.completion_init).parameters.values()
        if p.default is inspect.Parameter.empty
    ], "typer._completion_classes.completion_init needs an argument"


def test_get_completion_script_takes_the_keyword_arguments() -> None:
    parameters = inspect.signature(_completion_shared.get_completion_script).parameters
    for name in ("prog_name", "complete_var", "shell"):
        assert name in parameters, f"typer._completion_shared.get_completion_script lost the keyword {name}"
        assert parameters[name].kind in (
            inspect.Parameter.KEYWORD_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ), f"typer._completion_shared.get_completion_script takes {name} in another way"


@pytest.mark.parametrize(
    ("shell", "names"),
    [
        ("bash", ["COMP_WORDS", "COMP_CWORD", "complete_bash"]),
        ("zsh", ["_TYPER_COMPLETE_ARGS", "complete_zsh"]),
        ("fish", ["_TYPER_COMPLETE_ARGS", "_TYPER_COMPLETE_FISH_ACTION", "complete_fish"]),
    ],
)
def test_the_script_names_the_variables_of_the_protocol(shell: str, names: list[str]) -> None:
    script = _script(shell)
    for name in names:
        assert name in script, f"typer._completion_shared.get_completion_script({shell}) no longer names {name}"
    assert "_TLAUP_COMPLETE" in script


def test_the_registry_of_shells_exists_and_is_a_dictionary() -> None:
    registry: Any = getattr(shell_completion, "_available_shells", None)
    assert isinstance(registry, dict), "typer._click.shell_completion._available_shells is not a dictionary"
