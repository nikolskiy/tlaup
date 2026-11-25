"""``tlaup_parse`` and every module in it import with ``tlaup`` and the heavy libraries refused (design 10 P2)."""

from __future__ import annotations

import subprocess
import sys

REFUSED = ("tlaup", "rich", "typer", "pydantic", "requests", "yaml")

# The child puts a finder first on sys.meta_path that refuses the top-level names given as arguments, forgets
# any of them already imported, then imports tlaup_parse and every module found under it.
_CHILD = """
import sys

refused = frozenset(sys.argv[1:])


class Refuse:
    def find_spec(self, name, path=None, target=None):
        if name.partition(".")[0] in refused:
            raise ImportError(f"refused: {name}")
        return None


for loaded in list(sys.modules):
    if loaded.partition(".")[0] in refused:
        del sys.modules[loaded]
sys.meta_path.insert(0, Refuse())

import importlib
import pkgutil

import tlaup_parse

names = [info.name for info in pkgutil.walk_packages(tlaup_parse.__path__, "tlaup_parse.")]
for name in names:
    importlib.import_module(name)
print(len(names))
"""


def _run_child(refused: tuple[str, ...]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _CHILD, *refused], capture_output=True, text=True, check=False, timeout=60
    )


def test_package_imports_nothing_it_must_not() -> None:
    child = _run_child(REFUSED)
    assert child.returncode == 0, child.stderr
    assert int(child.stdout.strip()) >= 3  # model, values, exit_status at least: the walk found the modules


def test_the_check_can_fail() -> None:
    child = _run_child((*REFUSED, "dataclasses"))
    assert child.returncode != 0
    assert "refused: dataclasses" in child.stderr
