"""The isolation fixture's own tests (design 01 T2, "Tests")."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from tests.fakes.control import TOOLS

if TYPE_CHECKING:
    from tests.conftest import Isolated

LEAK_CHECK = "TLAUP_LEAK_CHECK"


def test_every_folder_of_app_paths_is_under_tmp_path(isolated: Isolated, tmp_path: Path) -> None:
    paths = isolated.paths
    folders = {"config": paths.config, "cache": paths.cache, "data": paths.data}
    files = {
        "config_file": paths.config_file,
        "tools": paths.tools / "written",
        "pin": paths.pin,
        "modules": paths.modules / "written",
        "runs": paths.runs / "written",
        "remote": paths.remote / "written",
        "java_cache": paths.java_cache,
    }
    files |= {name: folder / "written" for name, folder in folders.items()}
    for name, path in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name, encoding="utf-8")
        assert path.resolve().is_relative_to(tmp_path.resolve()), f"{name} is outside tmp_path: {path}"
    assert len(files) == 10  # config, cache, data and the seven derived paths


def test_leak_check_first() -> None:
    assert LEAK_CHECK not in os.environ
    os.environ[LEAK_CHECK] = "1"  # directly, not through monkeypatch: the one deliberate break of rule 7


def test_leak_check_second() -> None:
    assert LEAK_CHECK not in os.environ
    os.environ[LEAK_CHECK] = "1"  # directly, not through monkeypatch: the one deliberate break of rule 7


def test_path_holds_only_the_fakes(isolated: Isolated, tmp_path: Path) -> None:
    assert os.environ["PATH"] == str(isolated.bin)
    assert isolated.bin == tmp_path / "bin"
    for tool in TOOLS:
        assert shutil.which(tool) == str(isolated.bin / tool)
    assert sorted(path.name for path in isolated.bin.iterdir() if not path.name.endswith(".cmd")) == sorted(TOOLS)


def test_home_and_working_folder_are_under_tmp_path(isolated: Isolated, tmp_path: Path) -> None:
    assert os.environ["HOME"] == os.environ["USERPROFILE"] == str(isolated.home)
    assert isolated.home.parent == tmp_path
    assert isolated.work.parent == tmp_path
    assert isolated.work.is_dir()
    assert Path.cwd() == isolated.work
    assert os.environ["TLAUP_HOME"] == str(isolated.home / "tlaup")
