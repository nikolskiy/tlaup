"""The registered commands are exactly the tree of design 23 C1, written out by hand (package 48).

The tree below is not derived from the code: a command added, removed or renamed without updating design 23 C1
fails here. Arguments are `(name, required, variadic)` as Typer names them in the code (`tlc_args` is the
metavar `-- TLC ARGS` of the help); options are the long forms.
"""

import ast
import importlib.metadata
import importlib.util
import inspect
from pathlib import Path
from typing import Any

import typer.main
from typer.testing import CliRunner

import tlaup.cli
from tlaup.versioning.app_version import get_app_version

Arg = tuple[str, bool, bool]

JAVA = ("--auto-install", "--java-opt")
TREE: dict[str, tuple[tuple[Arg, ...], tuple[str, ...]]] = {
    "tlc": (
        (("spec", True, False), ("tlc_args", False, True)),
        (
            "--cfg",
            "--workers",
            "--coverage",
            "--raw",
            "--plain",
            "--keep",
            "--show-command",
            "--refresh-interval",
            *JAVA,
        ),
    ),
    "sany": ((("spec", True, False), ("sany_args", False, True)), JAVA),
    "pcal": ((("spec", True, False), ("pcal_args", False, True)), JAVA),
    "repl": ((("repl_args", False, True),), JAVA),
    "tool list": ((), ("--installed",)),
    "tool install": ((("version", False, False),), ("--force",)),
    "tool upgrade": ((("version", False, False),), ()),
    "tool uninstall": ((("versions", False, True),), ("--all", "--yes")),
    "tool pin": ((("version", True, False),), ()),
    "tool current": ((), ()),
    "tool dir": ((), ()),
    "tool path": ((("version", False, False),), ()),
    "module add": ((("path", True, False),), ()),
    "module list": ((), ()),
    "module dir": ((), ()),
    "module remove": ((("name", True, False),), ()),
    "config path": ((), ()),
    "config show": ((), ()),
    "config edit": ((), ()),
    "config get": ((("key", True, False),), ()),
    "config set": ((("key", True, False), ("value", True, False)), ()),
    "cache dir": ((), ()),
    "cache list": ((), ()),
    "cache clean": ((("run_id", False, False),), ("--runs", "--remote", "--all")),
    "doctor": ((), ()),
    "completion": ((("shell", True, False),), ()),
}
GROUPS = {"tool", "module", "config", "cache"}
ROOT_OPTIONS = {"--version", "-V", "--debug"}
SRC = Path(tlaup.__file__).parent


def _walk(command: Any, path: tuple[str, ...] = ()) -> dict[tuple[str, ...], Any]:
    found: dict[tuple[str, ...], Any] = {}
    for name, sub in command.commands.items() if hasattr(command, "commands") else ():
        found[(*path, name)] = sub
        found.update(_walk(sub, (*path, name)))
    return found


def _registered() -> dict[tuple[str, ...], Any]:
    return _walk(typer.main.get_command(tlaup.cli.app))


def _arguments(command: Any) -> tuple[Arg, ...]:
    return tuple((p.name, bool(p.required), p.nargs == -1) for p in command.params if p.param_type_name == "argument")


def _options(command: Any) -> list[str]:
    return [name for p in command.params if p.param_type_name == "option" for name in (*p.opts, *p.secondary_opts)]


def test_the_commands_are_the_tree() -> None:
    expected = {tuple(path.split()) for path in TREE} | {(group,) for group in GROUPS}
    assert set(_registered()) == expected


def test_each_command_has_its_arguments_and_long_options() -> None:
    registered = _registered()
    for path, (arguments, options) in TREE.items():
        command = registered[tuple(path.split())]
        assert _arguments(command) == arguments, f"arguments of tlaup {path}"
        assert sorted(o for o in _options(command) if o.startswith("--")) == sorted(options), f"options of {path}"


def test_the_groups_have_no_options_and_print_help_alone() -> None:
    registered = _registered()
    for group in GROUPS:
        command = registered[(group,)]
        assert command.params == [], group
        assert command.no_args_is_help, group


def test_the_root_options() -> None:
    root = typer.main.get_command(tlaup.cli.app)
    assert set(_options(root)) == ROOT_OPTIONS


def test_no_option_has_a_one_letter_form_but_the_version_flag() -> None:
    one_letter = {
        (path, name)
        for path, command in {(): typer.main.get_command(tlaup.cli.app), **_registered()}.items()
        for name in _options(command)
        if len(name) == 2 and name[0] == "-" and name[1] != "-"
    }
    assert one_letter == {((), "-V")}


def test_no_command_has_a_second_name() -> None:
    def names(command: Any) -> list[str]:
        sub = command.commands if hasattr(command, "commands") else {}
        return [*sub, *(n for child in sub.values() for n in names(child))]

    for path, command in _registered().items():
        assert command.name == path[-1], f"tlaup {' '.join(path)} is registered under {command.name!r}"
        assert len(set(getattr(command, "commands", {}))) == len(getattr(command, "commands", {}))
    assert len(names(typer.main.get_command(tlaup.cli.app))) == len(TREE) + len(GROUPS)


def test_the_two_version_flags_print_the_same_two_lines() -> None:
    runner = CliRunner()
    short, long = runner.invoke(tlaup.cli.app, ["-V"]), runner.invoke(tlaup.cli.app, ["--version"])
    assert short.exit_code == long.exit_code == 0
    assert short.stdout == long.stdout
    meta = importlib.metadata.metadata("tlaup")
    first, second = short.stdout.splitlines()
    assert short.stdout.count("\n") == 2
    assert first == f"tlaup {get_app_version(base_version=meta['Version'])}"
    assert second == meta["Summary"]


def test_registration_is_in_cli_py_alone() -> None:
    offending: list[str] = []
    for path in sorted((SRC / "cmd").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        for node in ast.walk(ast.parse(source)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"command", "add_typer", "callback"}
            ):
                offending.append(f"{path.relative_to(SRC)}:{node.lineno}: .{node.func.attr}(")
            if isinstance(node, ast.Import | ast.ImportFrom) and "noqa: F401" in lines[node.lineno - 1]:
                offending.append(f"{path.relative_to(SRC)}:{node.lineno}: an import for its side effect")
    assert offending == []


def test_nothing_old_is_left_importable() -> None:
    old = [
        "tlaup.cmd.tools",
        "tlaup.cmd.modules",
        "tlaup.cmd.fetch_cache",
        "tlaup.cmd.check_java",
        "tlaup.tlc.run_cache",
        "tlaup.tlc.compiler",
        "tlaup.java.inspector",
        "tlaup.versioning.paths",
    ]
    assert [name for name in old if importlib.util.find_spec(name) is not None] == []


def test_every_command_keeps_its_whole_help() -> None:
    """The one rule: a command function with a docstring is registered without `help=`, so its whole docstring
    is the help (a `help=` would replace the body paragraphs); one without a docstring is registered with HELP."""
    for path, command in _registered().items():
        if hasattr(command, "commands"):
            continue
        docstring = inspect.getdoc(command.callback)
        assert command.help, f"tlaup {' '.join(path)} has no help"
        if docstring is not None:
            assert command.help == docstring, f"tlaup {' '.join(path)} lost part of its docstring"
