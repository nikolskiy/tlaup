"""The version string and the one case where git is started (design 14 F9; inventory row P3)."""

import importlib.metadata
import json
from pathlib import Path

import pytest

from tests.fakes.control import Fakes
from tlaup.versioning.app_version import get_app_version, is_editable_install


def test_a_normal_install_does_not_start_git(fakes: Fakes) -> None:
    fakes.script("git", {})
    assert get_app_version("0.9.0", editable=False) == "0.9.0"
    assert fakes.log("git") == []


def test_a_development_install_shows_the_short_commit(fakes: Fakes) -> None:
    fakes.script("git", {"stdout": "abc1234\n"})
    assert get_app_version("0.9.0", editable=True) == "0.9.0+abc1234"
    starts = [line for line in fakes.log("git") if line["event"] == "start"]
    assert len(starts) == 1
    assert starts[0]["args"] == ["rev-parse", "--short", "HEAD"]


def test_no_git_on_path_leaves_the_plain_version(fakes: Fakes) -> None:
    fakes.remove("git")
    assert get_app_version("0.9.0", editable=True) == "0.9.0"


def test_a_failing_git_leaves_the_plain_version(fakes: Fakes) -> None:
    fakes.script("git", {"exit": 128, "stdout": ""})
    assert get_app_version("0.9.0", editable=True) == "0.9.0"


def test_the_base_version_comes_from_the_metadata_when_none_is_given() -> None:
    assert get_app_version(editable=False) == importlib.metadata.version("tlaup")


def dist_info(tmp_path: Path, direct_url: object | None) -> importlib.metadata.Distribution:
    folder = tmp_path / "tlaup-0.9.0.dist-info"
    folder.mkdir()
    (folder / "METADATA").write_text("Metadata-Version: 2.1\nName: tlaup\nVersion: 0.9.0\n", encoding="utf-8")
    if direct_url is not None:
        (folder / "direct_url.json").write_text(json.dumps(direct_url), encoding="utf-8")
    return importlib.metadata.PathDistribution(folder)


@pytest.mark.parametrize(
    ("direct_url", "expected"),
    [
        ({"url": "file:///x", "dir_info": {"editable": True}}, True),
        ({"url": "file:///x"}, False),
        (None, False),
    ],
    ids=["editable", "not editable", "no direct_url.json"],
)
def test_is_editable_install_reads_direct_url_json(tmp_path: Path, direct_url: object | None, expected: bool) -> None:
    assert is_editable_install(dist_info(tmp_path, direct_url)) is expected
