"""resolve_cfg and config_arg (design 11 R4 steps 4 and 5; research 16's rows F1 to F14, research 24's R1 to R10).

Every cfg holds its own path under the temporary folder, so a test tells files apart by reading them.
"""

from pathlib import Path

import pytest

from tlaup.errors import CfgNotFound, UsageError
from tlaup.project.core import find_project_root
from tlaup.project.spec import config_arg, resolve_cfg, resolve_spec


def _make(root: Path, *names: str) -> None:
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(name if name.endswith(".cfg") else "---- MODULE Spec ----\n====\n")


def _link(root: Path, link: str, target: str) -> None:
    (root / link).parent.mkdir(parents=True, exist_ok=True)
    try:
        (root / link).symlink_to(target, target_is_directory=not target.endswith(".tla"))
    except OSError:
        pytest.skip("links cannot be made")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """Research 16's tree under tmp_path."""
    _make(
        tmp_path,
        "proj/Spec.tla",
        "proj/Spec.cfg",
        "proj/a.cfg",
        "proj/sub/a.cfg",
        "proj/cfgs/b.cfg",
        "proj/my cfgs/with space.cfg",
        "outside/out.cfg",
        "work/Spec.cfg",
        "work/a.cfg",
        "work/sub/a.cfg",
        "rootproj/spec/Spec.tla",
        "rootproj/spec/Spec.cfg",
        "rootproj/spec/sib.cfg",
        "rootproj/cfgs/x.cfg",
        "rootproj/root.cfg",
        "rootproj/out.cfg",
        "rootproj/my cfgs/sp.cfg",
    )
    (tmp_path / "rootproj" / "lib").mkdir()
    (tmp_path / "rootproj" / "modules").mkdir()
    return tmp_path


# row, working folder, spec typed, cfg typed, validated file, -config value
F_ROWS = [
    ("F1", "rootproj", "spec/Spec", "sib", "rootproj/spec/sib.cfg", "sib.cfg"),
    ("F2", "rootproj", "spec/Spec", "cfgs/x.cfg", "rootproj/cfgs/x.cfg", "../cfgs/x.cfg"),
    ("F3", "rootproj", "spec/Spec", "my cfgs/sp.cfg", "rootproj/my cfgs/sp.cfg", "../my cfgs/sp.cfg"),
    ("F4", "rootproj", "spec/Spec", "../outside/out.cfg", "outside/out.cfg", "../../outside/out.cfg"),
    ("F5", "rootproj", "spec/Spec", "<T>/outside/out.cfg", "outside/out.cfg", "../../outside/out.cfg"),
    ("F5b", "rootproj", "spec/Spec", "<T>/outside/out", "outside/out.cfg", "../../outside/out.cfg"),
    ("F6", "rootproj", "spec/Spec", "out", "rootproj/out.cfg", "../out.cfg"),
    ("F7", "work", "<T>/rootproj/spec/Spec", "<T>/outside/out.cfg", "outside/out.cfg", "../../outside/out.cfg"),
    ("F8", "work", "<T>/rootproj/spec/Spec", "../outside/out.cfg", "outside/out.cfg", "../../outside/out.cfg"),
    ("F9", "work", "<T>/rootproj/spec/Spec", "<T>/rootproj/cfgs/x.cfg", "rootproj/cfgs/x.cfg", "../cfgs/x.cfg"),
    ("F11", "proj", "Spec", "../outside/out.cfg", "outside/out.cfg", "../outside/out.cfg"),
    ("F12", "work", "<T>/proj/Spec", "sub/a.cfg", "proj/sub/a.cfg", "sub/a.cfg"),
    ("F13", "proj", "Spec", "my cfgs/with space.cfg", "proj/my cfgs/with space.cfg", "my cfgs/with space.cfg"),
    ("F14", "proj", "Spec", "cfgs/b", "proj/cfgs/b.cfg", "cfgs/b.cfg"),
]


def _run(tmp: Path, work: str, spec_text: str, cfg_text: str) -> tuple[Path, Path]:
    cwd = tmp / work
    spec = resolve_spec(spec_text.replace("<T>", str(tmp)), cwd)
    root = find_project_root(spec, tmp / "home")
    return spec, resolve_cfg(cfg_text.replace("<T>", str(tmp)), spec, cwd, root)


@pytest.mark.parametrize(("row", "work", "spec_text", "cfg_text", "validated", "value"), F_ROWS)
def test_the_cfg_validated_is_the_cfg_tlc_gets_f_rows(
    tree: Path, row: str, work: str, spec_text: str, cfg_text: str, validated: str, value: str
) -> None:
    spec, cfg = _run(tree, work, spec_text, cfg_text)
    assert cfg.read_text() == validated, row
    arg = config_arg(cfg, spec)
    assert (spec.parent / arg).samefile(tree / validated)
    assert arg == value
    # no link is involved, so the lexical form of the Windows rule gives the same text
    assert config_arg(cfg, spec, platform="win32") == value


def test_f10_the_spec_comes_back_without_dotdot(tree: Path) -> None:
    assert resolve_spec("../rootproj/spec/Spec", tree / "work") == tree / "rootproj" / "spec" / "Spec.tla"


@pytest.fixture
def links(tmp_path: Path) -> Path:
    """Research 24's link tree under tmp_path."""
    _make(
        tmp_path,
        "real/proj/Spec.tla",
        "real/proj/Spec.cfg",
        "real/proj/sub/a.cfg",
        "real/out.cfg",
        "real/other/o.cfg",
        "outside/o.cfg",
        "L/out.cfg",
        "deep/a/b/Spec.tla",
        "deep/a/b/Spec.cfg",
        "deep/a/out.cfg",
        "deep/out.cfg",
        "L2/out.cfg",
        "Lf/Spec.cfg",
        "work/out.cfg",
    )
    _link(tmp_path, "L/lnk", "../real/proj")
    _link(tmp_path, "L2/lnk", "../deep/a/b")
    _link(tmp_path, "Lf/Spec.tla", "../real/proj/Spec.tla")
    return tmp_path


# row, spec typed, cfg typed, validated file, Linux/macOS value, Windows (lexical) value
R_ROWS = [
    ("R1", "L/lnk/Spec.tla", "L/lnk/../out.cfg", "real/out.cfg", "../out.cfg", "../out.cfg"),
    ("R2", "L/lnk/Spec.tla", "L/out.cfg", "L/out.cfg", "../../L/out.cfg", "../out.cfg"),
    ("R3", "L2/lnk/Spec.tla", "L2/lnk/../out.cfg", "deep/a/out.cfg", "../out.cfg", "../out.cfg"),
    ("R4", "L2/lnk/Spec.tla", "L2/lnk/../../out.cfg", "deep/out.cfg", "../../out.cfg", "../../out.cfg"),
    ("R5", "L2/lnk/Spec.tla", "L2/out.cfg", "L2/out.cfg", "../../../L2/out.cfg", "../out.cfg"),
    ("R6", "L2/lnk/Spec.tla", "work/out.cfg", "work/out.cfg", "../../../work/out.cfg", "../../work/out.cfg"),
    ("R7", "L2/lnk/Spec.tla", "outside/o.cfg", "outside/o.cfg", "../../../outside/o.cfg", "../../outside/o.cfg"),
    (
        "R8",
        "L/lnk/Spec.tla",
        "real/proj/sub/a.cfg",
        "real/proj/sub/a.cfg",
        "sub/a.cfg",
        "../../real/proj/sub/a.cfg",
    ),
    ("R9", "Lf/Spec.tla", "real/out.cfg", "real/out.cfg", "../real/out.cfg", "../real/out.cfg"),
    ("R10", "real/proj/Spec.tla", "outside/o.cfg", "outside/o.cfg", "../../outside/o.cfg", "../../outside/o.cfg"),
]


@pytest.mark.parametrize(("row", "spec_text", "cfg_text", "validated", "value", "lexical"), R_ROWS)
def test_the_cfg_validated_is_the_cfg_tlc_gets_through_links_r_rows(
    links: Path, row: str, spec_text: str, cfg_text: str, validated: str, value: str, lexical: str
) -> None:
    spec = resolve_spec(spec_text, links)
    assert spec == links / spec_text
    cfg = resolve_cfg(cfg_text, spec, links, None)
    assert cfg.read_text() == validated, row
    arg = config_arg(cfg, spec)
    # TLC joins the value to the spec's folder and lets the operating system walk it
    assert (spec.parent / arg).samefile(links / validated)
    assert arg == value
    assert config_arg(cfg, spec, platform="win32") == lexical


def test_a_file_named_as_typed_without_the_suffix_is_never_taken(tmp_path: Path) -> None:
    (tmp_path / "Spec.tla").write_text("x")
    (tmp_path / "foo").write_text("not a cfg")
    with pytest.raises(CfgNotFound):
        resolve_cfg("foo", tmp_path / "Spec.tla", tmp_path, None)


def test_a_name_without_the_suffix_finds_the_cfg(tmp_path: Path) -> None:
    (tmp_path / "foo").write_text("not a cfg")
    (tmp_path / "foo.cfg").write_text("cfg")
    assert resolve_cfg("foo", tmp_path / "Spec.tla", tmp_path, None) == tmp_path / "foo.cfg"


def test_an_absolute_path_without_the_suffix_gets_it(tmp_path: Path) -> None:
    _make(tmp_path, "elsewhere/x.cfg")
    got = resolve_cfg(str(tmp_path / "elsewhere" / "x"), tmp_path / "Spec.tla", tmp_path / "work", None)
    assert got == tmp_path / "elsewhere" / "x.cfg"


def test_an_absolute_path_is_the_only_one_tried(tmp_path: Path) -> None:
    _make(tmp_path, "work/x.cfg")
    with pytest.raises(CfgNotFound) as caught:
        resolve_cfg(str(tmp_path / "nowhere" / "x.cfg"), tmp_path / "Spec.tla", tmp_path / "work", None)
    assert (caught.value.details or "").splitlines()[1:] == [f"  {tmp_path / 'nowhere' / 'x.cfg'}"]


def test_an_empty_name_is_a_usage_error(tmp_path: Path) -> None:
    with pytest.raises(UsageError):
        resolve_cfg("", tmp_path / "Spec.tla", tmp_path, None)


def test_the_order_is_the_specs_folder_then_the_working_folder_then_the_root_row_s5(tmp_path: Path) -> None:
    for folder in ("proj", "work", "root"):
        _make(tmp_path, f"{folder}/same.cfg")
    spec = tmp_path / "proj" / "Spec.tla"
    args = (spec, tmp_path / "work", tmp_path / "root")
    assert resolve_cfg("same", *args) == tmp_path / "proj" / "same.cfg"
    (tmp_path / "proj" / "same.cfg").unlink()
    assert resolve_cfg("same", *args) == tmp_path / "work" / "same.cfg"
    (tmp_path / "work" / "same.cfg").unlink()
    assert resolve_cfg("same", *args) == tmp_path / "root" / "same.cfg"


def test_details_lists_the_paths_tried_and_a_folder_met_twice_once(tmp_path: Path) -> None:
    (tmp_path / "root").mkdir()
    spec = tmp_path / "work" / "Spec.tla"
    with pytest.raises(CfgNotFound) as caught:
        resolve_cfg("nope", spec, tmp_path / "work", tmp_path / "root")
    assert (caught.value.details or "").splitlines()[1:] == [
        f"  {tmp_path / 'work' / 'nope.cfg'}",
        f"  {tmp_path / 'root' / 'nope.cfg'}",
    ]


def test_a_folder_named_like_a_cfg_is_not_a_file(tmp_path: Path) -> None:
    (tmp_path / "x.cfg").mkdir()
    with pytest.raises(CfgNotFound):
        resolve_cfg("x", tmp_path / "Spec.tla", tmp_path, None)
