import sys
from pathlib import Path

import platformdirs
import pytest

from tlaup.errors import ConfigInvalid
from tlaup.paths import AppPaths

VARS = {"TLAUP_CONFIG_DIR": "config", "TLAUP_CACHE_DIR": "cache", "TLAUP_DATA_DIR": "data"}


def _abs(tmp_path: Path, name: str) -> str:
    return str(tmp_path / name)


def test_home_alone(tmp_path: Path) -> None:
    p = AppPaths.from_env({"TLAUP_HOME": _abs(tmp_path, "h")})
    assert (p.config, p.cache, p.data) == (tmp_path / "h" / "config", tmp_path / "h" / "cache", tmp_path / "h" / "data")


@pytest.mark.parametrize("var", VARS)
def test_single_variable_alone(tmp_path: Path, var: str) -> None:
    p = AppPaths.from_env({var: _abs(tmp_path, "x")})
    got = {"config": p.config, "cache": p.cache, "data": p.data}
    fallback = {
        "config": Path(platformdirs.user_config_dir("tlaup")),
        "cache": Path(platformdirs.user_cache_dir("tlaup")),
        "data": Path(platformdirs.user_data_dir("tlaup")),
    }
    for field, path in got.items():
        assert path == (tmp_path / "x" if field == VARS[var] else fallback[field])


@pytest.mark.parametrize("var", VARS)
def test_single_variable_wins_over_home(tmp_path: Path, var: str) -> None:
    p = AppPaths.from_env({"TLAUP_HOME": _abs(tmp_path, "h"), var: _abs(tmp_path, "x")})
    got = {"config": p.config, "cache": p.cache, "data": p.data}
    for field, path in got.items():
        assert path == (tmp_path / "x" if field == VARS[var] else tmp_path / "h" / field)


@pytest.mark.parametrize("var", ["TLAUP_HOME", *VARS])
@pytest.mark.parametrize("value", ["relative/path", "rel", ".", ""])
def test_relative_or_empty_value_is_config_invalid(var: str, value: str) -> None:
    with pytest.raises(ConfigInvalid, match=var):
        AppPaths.from_env({var: value})


def test_tilde_is_expanded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    p = AppPaths.from_env({"TLAUP_HOME": "~/t", "TLAUP_DATA_DIR": "~"})
    assert p.config == tmp_path / "t" / "config"
    assert p.data == tmp_path


def test_fallback_is_platformdirs_row_c1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Preserved-behaviour row C1: config.yaml in the config folder, tools and modules in the cache folder."""
    for var in ("TLAUP_HOME", *VARS):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xc"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xk"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xd"))
    p = AppPaths.from_env({})
    assert p.config == Path(platformdirs.user_config_dir("tlaup"))
    assert p.cache == Path(platformdirs.user_cache_dir("tlaup"))
    assert p.data == Path(platformdirs.user_data_dir("tlaup"))
    assert p.config_file == p.config / "config.yaml"
    assert p.tools.parent == p.cache
    assert p.modules.parent == p.cache
    if sys.platform.startswith("linux"):
        assert p.config == tmp_path / "xc" / "tlaup"
        assert p.cache == tmp_path / "xk" / "tlaup"
        assert p.data == tmp_path / "xd" / "tlaup"


def test_derived_properties(tmp_path: Path) -> None:
    p = AppPaths.from_env({"TLAUP_HOME": str(tmp_path)})
    assert p.config_file == tmp_path / "config" / "config.yaml"
    assert p.tools == tmp_path / "cache" / "tool"
    assert p.pin == tmp_path / "cache" / "tool" / "pin"
    assert p.modules == tmp_path / "cache" / "module"
    assert p.runs == tmp_path / "cache" / "runs"
    assert p.remote == tmp_path / "cache" / "remote"
    assert p.java_cache == tmp_path / "cache" / "java.json"


def test_nothing_is_created(tmp_path: Path) -> None:
    home = tmp_path / "h"
    p = AppPaths.from_env({"TLAUP_HOME": str(home)})
    for prop in (p.config_file, p.tools, p.pin, p.modules, p.runs, p.remote, p.java_cache):
        assert isinstance(prop, Path)
    assert not home.exists()
    assert list(tmp_path.iterdir()) == []
