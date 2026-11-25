"""Module names and the registry of <cache>/module/ (design 13 M1, M2; inventory row M18)."""

from __future__ import annotations

import json
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from tests.clock import FakeClock
from tlaup.errors import InvalidName, ModuleNotFound, StoreLocked
from tlaup.modules.registry import RegisteredModule, Registry, read_record, validate_module_name, write_record

if TYPE_CHECKING:
    from pathlib import Path

    from tests.conftest import Isolated

INVALID = ["../tools", "../tool", "..", ".", "", "/abs", "a/b", "a\\b", ".hidden", ".tmp", "C:x", "my module", "a" * 65]
VALID = ["Queue", "a", "x.y_z-1", "b" * 64]


@pytest.fixture
def registry(isolated: Isolated) -> Registry:
    return Registry(isolated.paths.modules, now=FakeClock().now)


def register(registry: Registry, name: str, **fields: object) -> RegisteredModule:
    """A registered module as build_module leaves one: its folder and its module.json."""
    folder = registry.root / name
    folder.mkdir(parents=True)
    values: dict[str, object] = {
        "built_at": "2026-11-15T00:00:00Z",
        "source": "/src",
        "javac": None,
        "release": None,
        "built_against": None,
        "override_classes": (),
    }
    values.update(fields)
    module = RegisteredModule(name=name, path=folder, **values)  # type: ignore[arg-type]
    write_record(folder, module)
    return module


@pytest.mark.parametrize("name", INVALID)
def test_invalid_names_are_refused(name: str) -> None:
    with pytest.raises(InvalidName):
        validate_module_name(name)


@pytest.mark.parametrize("name", VALID)
def test_valid_names_come_back_unchanged(name: str) -> None:
    assert validate_module_name(name) == name


@pytest.mark.parametrize("name", INVALID)
def test_path_of_refuses_invalid_names(registry: Registry, name: str) -> None:
    with pytest.raises(InvalidName):
        registry.path_of(name)


def test_path_of_a_valid_name(registry: Registry) -> None:
    assert registry.path_of("Queue") == registry.root / "Queue"


def test_path_of_a_link_pointing_outside_the_root(registry: Registry, tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    registry.root.mkdir(parents=True)
    try:
        (registry.root / "Queue").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symbolic links cannot be made here: {error}")
    with pytest.raises(InvalidName, match="outside"):
        registry.path_of("Queue")


def test_list_with_no_root(registry: Registry) -> None:
    assert registry.list() == []
    assert not registry.root.exists()


def test_list_returns_only_registered_modules(registry: Registry) -> None:
    queue = register(
        registry, "Queue", javac="25.0.5", release=11, built_against="rolling@abc", override_classes=("a.B",)
    )
    (registry.root / ".tmp" / "20261115T000000Z-00").mkdir(parents=True)
    (registry.root / ".lock").write_text("")
    (registry.root / "Bare").mkdir()
    (registry.root / "Corrupt").mkdir()
    (registry.root / "Corrupt" / "module.json").write_text("{not json")
    future = register(registry, "Future")
    (future.path / "module.json").write_text(
        json.dumps({**json.loads((future.path / "module.json").read_text()), "schema": 99})
    )
    (registry.root / "Loose.json").write_text("{}")
    assert registry.list() == [queue]


def test_list_is_in_name_order_row_m18(registry: Registry) -> None:
    for name in ("Zeta", "alpha", "Beta"):
        register(registry, name)
    assert [module.name for module in registry.list()] == ["Beta", "Zeta", "alpha"]


def test_module_json_round_trip(registry: Registry) -> None:
    module = register(
        registry, "Queue", javac="25.0.5", release=11, built_against="rolling@abc", override_classes=("a.B", "a.C")
    )
    data = json.loads((module.path / "module.json").read_text(encoding="utf-8"))
    assert data == {
        "schema": 1,
        "name": "Queue",
        "built_at": "2026-11-15T00:00:00Z",
        "source": "/src",
        "javac": "25.0.5",
        "release": 11,
        "built_against": "rolling@abc",
        "override_classes": ["a.B", "a.C"],
    }
    assert read_record(module.path) == module
    assert sorted(path.name for path in module.path.iterdir()) == ["module.json"]


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("release", "11"),
        ("release", True),
        ("javac", 25),
        ("override_classes", "a.B"),
        ("built_at", None),
        ("name", "x"),
    ],
)
def test_a_record_of_the_wrong_shape_is_not_read(registry: Registry, key: str, value: object) -> None:
    module = register(registry, "Queue")
    data = json.loads((module.path / "module.json").read_text())
    data[key] = value
    (module.path / "module.json").write_text(json.dumps(data))
    assert read_record(module.path) is None


def test_remove(registry: Registry) -> None:
    register(registry, "Queue")
    other = register(registry, "Other")
    registry.remove("Queue")
    assert registry.list() == [other]
    left = sorted(path.name for path in registry.root.iterdir() if path.name not in (".tmp", ".lock"))
    assert left == ["Other"]
    assert list((registry.root / ".tmp").iterdir()) == []


def test_remove_an_unknown_name(registry: Registry) -> None:
    with pytest.raises(ModuleNotFound) as caught:
        registry.remove("Queue")
    assert caught.value.hint == "run `tlaup module list`"
    register(registry, "Other")
    (registry.root / "Bare").mkdir()
    for name in ("Queue", "Bare"):
        with pytest.raises(ModuleNotFound):
            registry.remove(name)
    assert (registry.root / "Bare").is_dir()


def test_remove_does_not_leave_the_root(registry: Registry) -> None:
    register(registry, "Other")
    tool = registry.root.parent / "tool"
    tool.mkdir()
    (tool / "pin").write_text("rolling\n")
    with pytest.raises(InvalidName):
        registry.remove("../tool")
    assert (tool / "pin").read_text() == "rolling\n"


HOLD = """
import sys, time, filelock
lock = filelock.FileLock(sys.argv[1])
lock.acquire(timeout=10)
print("held", flush=True)
sys.stdin.read()
"""


def test_locked_while_another_process_holds_it(registry: Registry) -> None:
    registry.root.mkdir(parents=True)
    lock_file = registry.root / ".lock"
    argv = [sys.executable, "-c", HOLD, str(lock_file)]
    with subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True) as holder:
        assert holder.stdin is not None
        assert holder.stdout is not None
        try:
            assert holder.stdout.readline().strip() == "held"
            with pytest.raises(StoreLocked) as caught, registry.locked(timeout=0.1):
                pass
            assert str(lock_file) in caught.value.message
        finally:
            holder.stdin.close()
            holder.wait(timeout=10)
    with registry.locked(timeout=1):
        assert lock_file.exists()
