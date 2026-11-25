"""No module under src/tlaup imports click or a private Typer module (design 14 F10).

Typer carries its own copy of Click as `typer._click`; `click` is not installed. Package 47 adds the one
exception, `tlaup/cmd/completion.py`.
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "tlaup"
EXCEPTIONS: frozenset[str] = frozenset()


def _forbidden(module: str) -> bool:
    parts = module.split(".")
    if parts[0] == "click":
        return True
    return parts[0] == "typer" and any(part.startswith("_") for part in parts[1:])


def _imports(tree: ast.AST) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.lineno, node.module))
            found.extend((node.lineno, f"{node.module}.{alias.name}") for alias in node.names)
    return found


def test_the_check_itself() -> None:
    assert _forbidden("click")
    assert _forbidden("click.core")
    assert _forbidden("typer._click")
    assert _forbidden("typer._completion_shared")
    assert not _forbidden("typer")
    assert not _forbidden("typer.core")
    assert not _forbidden("typer.core.TyperGroup")
    tree = ast.parse("from typer import _click\nimport click\nfrom typer.core import TyperGroup\n")
    assert [name for _, name in _imports(tree) if _forbidden(name)] == ["typer._click", "click"]


def test_no_private_imports() -> None:
    modules = sorted(SRC.rglob("*.py"))
    assert modules, f"no modules found under {SRC}"
    offending = []
    for path in modules:
        relative = path.relative_to(SRC.parent).as_posix()
        if relative in EXCEPTIONS:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offending.extend(f"{relative}:{line}: {name}" for line, name in _imports(tree) if _forbidden(name))
    assert offending == [], "imports of click or private Typer modules:\n" + "\n".join(offending)
