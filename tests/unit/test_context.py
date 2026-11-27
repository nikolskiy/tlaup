from collections.abc import Iterator
from pathlib import Path

import pytest

from tlaup import context
from tlaup.errors import ConfigInvalid
from tlaup.ui import Ui


@pytest.fixture(autouse=True)
def _fresh_context() -> Iterator[None]:
    context.reset()
    yield
    context.reset()


def test_get_context_is_cached_and_reset_rebuilds(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TLAUP_HOME", str(tmp_path / "a"))
    first = context.get_context()
    assert context.get_context() is first
    monkeypatch.setenv("TLAUP_HOME", str(tmp_path / "b"))
    assert context.get_context() is first
    context.reset()
    second = context.get_context()
    assert second is not first
    assert second.paths.config == tmp_path / "b" / "config"
    assert second.env["TLAUP_HOME"] == str(tmp_path / "b")


@pytest.mark.parametrize(("value", "expected"), [("1", True), ("0", False), ("true", False), (None, False)])
def test_debug_follows_tlaup_debug(monkeypatch: pytest.MonkeyPatch, value: str | None, expected: bool) -> None:
    if value is None:
        monkeypatch.delenv("TLAUP_DEBUG", raising=False)
    else:
        monkeypatch.setenv("TLAUP_DEBUG", value)
    assert context.get_context().debug is expected


def test_context_carries_a_ui() -> None:
    assert isinstance(context.get_context().ui, Ui)


def test_build_context_replaces_the_cached_one(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    first = context.get_context()
    built = context.build_context({"TLAUP_HOME": str(tmp_path)}, debug=False)
    assert built is not first
    assert context.get_context() is built
    assert built.paths.config == tmp_path / "config"


@pytest.mark.parametrize(
    ("flag", "variable", "expected"), [(False, None, False), (True, None, True), (False, "1", True)]
)
def test_build_context_debug_is_the_flag_or_tlaup_debug(
    flag: bool, variable: str | None, expected: bool, tmp_path: Path
) -> None:
    env = {"TLAUP_HOME": str(tmp_path)} | ({"TLAUP_DEBUG": variable} if variable else {})
    assert context.build_context(env, debug=flag).debug is expected


def test_build_context_that_fails_leaves_no_context_behind(tmp_path: Path) -> None:
    context.build_context({"TLAUP_HOME": str(tmp_path)}, debug=False)
    with pytest.raises(ConfigInvalid):
        context.build_context({"TLAUP_HOME": "relative"}, debug=False)
    assert context.get_context().paths.config != tmp_path / "config"
