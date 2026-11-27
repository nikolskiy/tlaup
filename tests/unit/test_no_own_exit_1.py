"""tlaup never returns 1 itself (design 02 X1, rule 1), checked over the source (package 48).

The forms the old code used are caught; a 1 held in a variable is the reviewer's to find.
"""

import ast
from pathlib import Path

import tlaup
import tlaup_parse

ROOTS = (Path(tlaup.__file__).parent, Path(tlaup_parse.__file__).parent)
EXIT_NAMES = {"Exit", "exit", "SystemExit"}
QUESTIONS = {"prompt", "confirm", "Prompt", "Confirm"}
# `typer.Exit(<expression>)`: a wrapped tool's code passing through (rule 2), and the tool commands' own
# result codes (2 to 5, from D29's table; `uninstall`'s 5 for a build that could not be removed).
EXPRESSION_EXITS = {
    "cmd/pcal.py": 1,
    "cmd/repl.py": 1,
    "cmd/sany.py": 1,
    "cmd/tlc.py": 1,
    "cmd/tool/current.py": 1,
    "cmd/tool/install.py": 1,
    "cmd/tool/list.py": 1,
    "cmd/tool/pin.py": 1,
    "cmd/tool/path.py": 1,
    "cmd/tool/uninstall.py": 1,
    "cmd/tool/upgrade.py": 1,
}


def _files() -> list[Path]:
    return sorted(path for root in ROOTS for path in root.rglob("*.py"))


def _name(func: ast.expr) -> str | None:
    if isinstance(func, ast.Attribute):
        return func.attr
    return func.id if isinstance(func, ast.Name) else None


def _is_one(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is not False and node.value == 1  # 1 and True


def _exit_calls(tree: ast.AST) -> list[ast.Call]:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and _name(n.func) in EXIT_NAMES]


def _argument(call: ast.Call) -> ast.expr | None:
    if call.args:
        return call.args[0]
    return next((k.value for k in call.keywords if k.arg == "code"), None)


def test_no_exit_with_the_literal_one() -> None:
    offending = []
    for path in _files():
        for call in _exit_calls(ast.parse(path.read_text(encoding="utf-8"))):
            argument = _argument(call)
            if argument is not None and _is_one(argument):
                offending.append(f"{path.name}:{call.lineno}")
    assert offending == []


def test_the_exits_with_an_expression_are_the_listed_ones() -> None:
    found: dict[str, int] = {}
    for root in ROOTS:
        for path in sorted(root.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            count = 0
            for call in _exit_calls(tree):
                argument = _argument(call)
                if argument is not None and not isinstance(argument, ast.Constant):
                    count += 1
            if count and root.name == "tlaup" and path.name != "cli.py":
                found[path.relative_to(root).as_posix()] = count
    assert found == EXPRESSION_EXITS


def test_no_question_is_asked_but_through_ui_ask() -> None:
    offending = []
    for path in _files():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and _name(node.func) in QUESTIONS:
                offending.append(f"{path.name}:{node.lineno}")
    assert offending == []


def test_typer_echo_is_only_in_ui_and_the_reporters() -> None:
    allowed = {"ui.py"}
    offending = []
    for path in _files():
        if path.name in allowed or "reporters" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and _name(node.func) == "echo":
                offending.append(f"{path.name}:{node.lineno}")
    assert offending == []


def test_ui_has_none_of_the_four_old_functions() -> None:
    tree = ast.parse((Path(tlaup.__file__).parent / "ui.py").read_text(encoding="utf-8"))
    top = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert top.isdisjoint({"warn", "error", "info", "success"})
