"""resolve_spec (design 11 R5 and R4 step 3; inventory rows S1 to S4)."""

import os
from pathlib import Path

import pytest

from tlaup.errors import SpecNotFound, UsageError
from tlaup.project.spec import resolve_spec


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n")
    return path


def _link(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except OSError:
        pytest.skip("links cannot be made")


# (text, files made under the working folder, expected file or None for "not found")
FOUND = [
    ("Foo", ["Foo.tla"], "Foo.tla"),
    ("Foo.tla", ["Foo.tla"], "Foo.tla"),
    ("Foo.v2", ["Foo.v2.tla"], "Foo.v2.tla"),
    ("Foo.v2", ["Foo.tla"], None),
    ("dir/Foo", ["dir/Foo.tla"], "dir/Foo.tla"),
    ("Foo", ["spec/Foo.tla"], "spec/Foo.tla"),
    ("Foo", ["Foo.tla", "spec/Foo.tla"], "Foo.tla"),
    ("Foo", ["Foo/x.txt", "Foo.tla"], "Foo.tla"),
    ("Foo/", ["Foo/x.txt", "Foo.tla"], "Foo.tla"),
    # the seven cases of 0.8.x's test_resolution_scenarios.py (row S1 to S4)
    ("my_model.tla", ["my_model.tla"], "my_model.tla"),
    ("my_model", ["my_model.tla"], "my_model.tla"),
    ("my_model", ["spec/my_model.tla"], "spec/my_model.tla"),
    ("missing", [], None),
    ("subdir/my_model", ["subdir/my_model.tla"], "subdir/my_model.tla"),
    ("subdir/my_model", ["subdir/spec/my_model.tla"], "subdir/spec/my_model.tla"),
    ("subdir/missing", ["subdir/other.tla"], None),
]


@pytest.mark.parametrize(("text", "files", "expected"), FOUND)
def test_names_resolve(tmp_path: Path, text: str, files: list[str], expected: str | None) -> None:
    for name in files:
        _touch(tmp_path / name)
    if expected is None:
        with pytest.raises(SpecNotFound):
            resolve_spec(text, tmp_path)
        return
    got = resolve_spec(text, tmp_path)
    assert got == tmp_path / expected
    assert got.is_absolute()
    assert got.is_file()


@pytest.mark.parametrize("text", ["", ".", ".."])
def test_empty_dot_and_dotdot_are_usage_errors(tmp_path: Path, text: str) -> None:
    with pytest.raises(UsageError, match="SPEC must be a TLA\\+ file or its name"):
        resolve_spec(text, tmp_path)


def test_a_cfg_is_never_a_spec_and_the_hint_needs_the_tla_beside_it(tmp_path: Path) -> None:
    _touch(tmp_path / "Foo.cfg")
    with pytest.raises(SpecNotFound) as bare:
        resolve_spec("Foo.cfg", tmp_path)
    assert bare.value.hint is None
    _touch(tmp_path / "Foo.tla")
    with pytest.raises(SpecNotFound) as beside:
        resolve_spec("Foo.cfg", tmp_path)
    assert beside.value.hint == "did you mean Foo.tla?"


def test_a_folder_alone_is_a_usage_error(tmp_path: Path) -> None:
    (tmp_path / "Foo").mkdir()
    with pytest.raises(UsageError, match="SPEC is a folder"):
        resolve_spec("Foo", tmp_path)


def test_a_tla_name_that_is_a_folder_is_not_a_spec(tmp_path: Path) -> None:
    (tmp_path / "Foo.tla").mkdir()
    with pytest.raises(SpecNotFound):
        resolve_spec("Foo.tla", tmp_path)


def test_details_lists_every_path_tried_in_order(tmp_path: Path) -> None:
    with pytest.raises(SpecNotFound) as caught:
        resolve_spec("sub/Foo.v2", tmp_path)
    lines = [line.strip() for line in (caught.value.details or "").splitlines()[1:]]
    assert lines == [str(tmp_path / "sub" / "Foo.v2.tla"), str(tmp_path / "sub" / "spec" / "Foo.v2.tla")]
    with pytest.raises(SpecNotFound) as with_suffix:
        resolve_spec("Foo.tla", tmp_path)
    assert (with_suffix.value.details or "").splitlines()[1:] == [f"  {tmp_path / 'Foo.tla'}"]


def test_an_absolute_text_ignores_the_working_folder(tmp_path: Path) -> None:
    spec = _touch(tmp_path / "a" / "Foo.tla")
    other = tmp_path / "b"
    other.mkdir()
    assert resolve_spec(str(tmp_path / "a" / "Foo"), other) == spec


def test_a_linked_folder_keeps_the_path_the_user_named(tmp_path: Path) -> None:
    real = _touch(tmp_path / "real" / "Spec.tla").parent
    _link(tmp_path / "L" / "lnk", real)
    got = resolve_spec("L/lnk/Spec", tmp_path)
    assert got == tmp_path / "L" / "lnk" / "Spec.tla"


def test_a_link_to_the_file_keeps_the_path_the_user_named(tmp_path: Path) -> None:
    real = _touch(tmp_path / "real" / "Spec.tla")
    _link(tmp_path / "Lf" / "Spec.tla", real)
    assert resolve_spec("Lf/Spec", tmp_path) == tmp_path / "Lf" / "Spec.tla"


def test_dotdot_is_removed_as_text_when_it_names_the_same_file_row_f10(tmp_path: Path) -> None:
    spec = _touch(tmp_path / "rootproj" / "spec" / "Spec.tla")
    work = tmp_path / "work"
    work.mkdir(exist_ok=True)
    got = resolve_spec("../rootproj/spec/Spec", work)
    assert got == spec
    assert ".." not in got.parts


@pytest.fixture
def dotdot_after_link(tmp_path: Path) -> Path:
    _touch(tmp_path / "real" / "proj" / "Spec.tla")
    _link(tmp_path / "L" / "lnk", tmp_path / "real" / "proj")
    # L/lnk/../proj/Spec.tla is real/proj/Spec.tla for the system; the textual L/proj/Spec.tla does not exist
    assert not (tmp_path / "L" / "proj").exists()
    return tmp_path


def test_dotdot_after_a_link_stays_in_place(dotdot_after_link: Path) -> None:
    got = resolve_spec("L/lnk/../proj/Spec.tla", dotdot_after_link)
    assert got == Path(os.path.join(dotdot_after_link, "L/lnk/../proj/Spec.tla"))
    assert got.is_file()


def test_dotdot_after_a_link_is_not_found_on_windows(dotdot_after_link: Path) -> None:
    with pytest.raises(SpecNotFound):
        resolve_spec("L/lnk/../proj/Spec.tla", dotdot_after_link, platform="win32")


def test_the_textual_form_is_used_on_windows_when_it_names_the_same_file(tmp_path: Path) -> None:
    spec = _touch(tmp_path / "proj" / "Spec.tla")
    (tmp_path / "work").mkdir(exist_ok=True)
    assert resolve_spec("../proj/Spec", tmp_path / "work", platform="win32") == spec
