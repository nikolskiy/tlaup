from collections.abc import Iterator
from pathlib import Path

import pytest

from tlaup import context
from tlaup.config import loader
from tlaup.versioning import paths as vpaths


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


def test_old_code_follows_the_variables(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("TLAUP_HOME", str(tmp_path))
    assert loader.config_dir() == tmp_path / "config"
    assert loader.cache_dir() == tmp_path / "cache"
    assert vpaths.get_tools_dir() == tmp_path / "cache" / "tools"
