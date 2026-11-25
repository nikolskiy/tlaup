"""The check of scripts/test_clean.py, on home folders the test makes."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

SCRIPT = Path(__file__).parents[2] / "scripts" / "test_clean.py"


@pytest.fixture
def clean_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("test_clean_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_empty_home_has_none(clean_script: ModuleType, tmp_path: Path) -> None:
    assert clean_script.find_tlaup_folders(tmp_path) == []
    assert clean_script.main(["--home", str(tmp_path)]) == 0


@pytest.mark.parametrize("folder", [".cache/tlaup", "Library/Application Support/tlaup", ".tlaplus"])
def test_a_tlaup_folder_is_found(
    clean_script: ModuleType, tmp_path: Path, folder: str, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / folder).mkdir(parents=True)
    assert clean_script.find_tlaup_folders(tmp_path) == [tmp_path / folder]
    assert clean_script.main(["--home", str(tmp_path)]) == 1
    assert str(tmp_path / folder) in capsys.readouterr().err


def test_an_unrelated_folder_is_not_reported(clean_script: ModuleType, tmp_path: Path) -> None:
    (tmp_path / ".cache" / "other").mkdir(parents=True)
    (tmp_path / ".config" / "tlaup-like").mkdir(parents=True)
    assert clean_script.find_tlaup_folders(tmp_path) == []
    assert clean_script.main(["--home", str(tmp_path)]) == 0
