"""find_project_root (design 11 R10; inventory rows S8, S9 and S13)."""

import os
from pathlib import Path

import pytest

from tlaup.project.core import find_project_root

MARKERS = ["classes", "lib", "modules"]


def _spec(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    spec = folder / "Spec.tla"
    spec.write_text("---- MODULE Spec ----\n====\n")
    return spec


@pytest.fixture
def home(tmp_path: Path) -> Path:
    path = tmp_path / "home"
    path.mkdir(exist_ok=True)
    return path


def test_the_specs_own_folder_holds_classes(tmp_path: Path, home: Path) -> None:
    spec = _spec(tmp_path / "proj")
    (tmp_path / "proj" / "classes").mkdir()
    assert find_project_root(spec, home) == tmp_path / "proj"


def test_nothing_anywhere_is_no_root(tmp_path: Path, home: Path) -> None:
    assert find_project_root(_spec(tmp_path / "proj"), home) is None


@pytest.mark.parametrize("marker", MARKERS)
def test_the_own_folder_marker_counts_row_s13_s8(tmp_path: Path, home: Path, marker: str) -> None:
    spec = _spec(tmp_path / "proj" / "sub")
    (tmp_path / "proj" / "sub" / marker).mkdir()
    assert find_project_root(spec, home) == tmp_path / "proj" / "sub"


@pytest.mark.parametrize("marker", MARKERS)
def test_the_parent_of_a_spec_folder_holds_a_marker(tmp_path: Path, home: Path, marker: str) -> None:
    spec = _spec(tmp_path / "proj" / "spec")
    (tmp_path / "proj" / marker).mkdir()
    assert find_project_root(spec, home) == tmp_path / "proj"


@pytest.mark.parametrize("name", ["spec", "specs", "test", "tests"])
def test_the_four_folder_names_allow_the_parent_row_s9(tmp_path: Path, home: Path, name: str) -> None:
    spec = _spec(tmp_path / "proj" / name)
    (tmp_path / "proj" / "modules").mkdir()
    assert find_project_root(spec, home) == tmp_path / "proj"


def test_the_own_folder_wins_over_the_parent(tmp_path: Path, home: Path) -> None:
    spec = _spec(tmp_path / "proj" / "spec")
    (tmp_path / "proj" / "lib").mkdir()
    (tmp_path / "proj" / "spec" / "modules").mkdir()
    assert find_project_root(spec, home) == tmp_path / "proj" / "spec"


def test_a_parent_with_lib_and_a_folder_not_named_spec_is_no_root(tmp_path: Path, home: Path) -> None:
    spec = _spec(tmp_path / "work")
    (tmp_path / "lib").mkdir()
    assert find_project_root(spec, home) is None


def test_the_names_are_compared_as_written(tmp_path: Path, home: Path) -> None:
    spec = _spec(tmp_path / "proj" / "Spec")
    (tmp_path / "proj" / "lib").mkdir()
    assert find_project_root(spec, home) is None


def test_the_parent_is_the_home_folder(home: Path) -> None:
    spec = _spec(home / "spec")
    (home / "lib").mkdir()
    assert find_project_root(spec, home) is None


def test_the_specs_folder_is_the_home_folder(home: Path) -> None:
    spec = _spec(home)
    (home / "lib").mkdir()
    assert find_project_root(spec, home) is None


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="links cannot be made")
def test_a_home_folder_reached_through_a_link_is_still_refused(tmp_path: Path, home: Path) -> None:
    spec = _spec(home / "spec")
    (home / "lib").mkdir()
    link = tmp_path / "homelink"
    try:
        link.symlink_to(home, target_is_directory=True)
    except OSError:
        pytest.skip("links cannot be made")
    assert find_project_root(link / "spec" / "Spec.tla", home) is None
    assert find_project_root(spec, link) is None


def test_the_filesystem_root_is_never_a_root(home: Path) -> None:
    root = Path(Path.cwd().anchor)
    assert find_project_root(root / "Spec.tla", home) is None


def test_the_root_returned_is_built_from_the_path_as_given(tmp_path: Path, home: Path) -> None:
    spec = _spec(tmp_path / "proj" / "spec")
    (tmp_path / "proj" / "lib").mkdir()
    assert find_project_root(spec, home) == tmp_path / "proj"
    assert find_project_root(spec, home).is_absolute()  # type: ignore[union-attr]
