"""The completers, called directly (design 23 C3; package 47)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from tests.clock import FakeClock
from tests.steps._store import add_build, published_jars, recorded_releases
from tlaup.cmd.completion import (
    complete_config_key,
    complete_install,
    complete_installed,
    complete_module,
    complete_spec,
    complete_upgrade,
)
from tlaup.config.schema import setting_keys
from tlaup.modules.registry import RegisteredModule, write_record
from tlaup.versioning.remote import cached_tags, write_cache
from tlaup.versioning.spec import format_build
from tlaup.versioning.store import ToolStore

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.conftest import Isolated

ROLLING_ONE = "rolling@1a2b3c4"
ROLLING_TWO = "rolling@5d6e7f8"


def prepare_store(isolated: Isolated, folder: Path) -> list[str]:
    """Two builds of rolling with different commits and v1.7.4; the words of the printed forms."""
    store = ToolStore(isolated.paths, now=FakeClock().now)
    add_build(store, folder, "v1.7.4", pinned=True)
    add_build(store, folder, ROLLING_ONE)
    add_build(store, folder, ROLLING_TWO)
    builds = store.builds()
    return [format_build(build, builds) for build in builds]


# Every completer that works out the folders from the environment; complete_config_key reads no path.
PATH_COMPLETERS: list[Callable[[str], list[str]]] = [
    complete_installed,
    complete_upgrade,
    complete_install,
    complete_module,
]


def test_installed_gives_every_printed_form_each_name_stable_and_rolling_once(
    isolated: Isolated, tmp_path: Path
) -> None:
    printed = prepare_store(isolated, tmp_path)
    words = complete_installed("")
    assert sorted(words) == sorted({*printed, "rolling", "v1.7.4", "stable"})
    assert len(words) == len(set(words))
    assert {"rolling", "stable"} <= set(words)
    assert any(word.startswith("rolling@") for word in words)


def test_installed_with_a_prefix_gives_only_the_words_that_start_with_it(isolated: Isolated, tmp_path: Path) -> None:
    prepare_store(isolated, tmp_path)
    words = complete_installed("rol")
    assert words
    assert all(word.startswith("rol") for word in words)
    assert "stable" not in words
    assert "v1.7.4" not in words


def test_a_broken_build_json_does_not_stop_the_rest(isolated: Isolated, tmp_path: Path) -> None:
    prepare_store(isolated, tmp_path)
    broken = isolated.paths.tools / "broken-1234"
    broken.mkdir()
    (broken / "build.json").write_text("not json", encoding="utf-8")
    (broken / "tla2tools.jar").write_bytes(b"x")
    words = complete_installed("")
    assert "v1.7.4" in words
    assert "rolling" in words


def test_upgrade_gives_names_only(isolated: Isolated, tmp_path: Path) -> None:
    prepare_store(isolated, tmp_path)
    words = complete_upgrade("")
    assert sorted(words) == ["rolling", "v1.7.4"]
    assert not any("@" in word for word in words)


def test_install_without_a_cache_gives_stable_and_rolling(isolated: Isolated) -> None:
    assert complete_install("") == ["stable", "rolling"]


def test_install_with_a_remembered_release_list_adds_the_recorded_tags_that_have_the_jar(
    isolated: Isolated, tmp_path: Path
) -> None:
    # No `github` fixture and the sockets are blocked: a request would fail this test.
    url = "https://api.github.com/repos/tlaplus/tlaplus/releases"
    releases = recorded_releases("releases", published_jars(tmp_path))
    write_cache(isolated.paths.remote, url, releases, datetime(2020, 1, 1, tzinfo=UTC))  # old: age is ignored
    with_jar = {r["tag_name"] for r in releases if any(a.get("name") == "tla2tools.jar" for a in r["assets"])}
    without_jar = {r["tag_name"] for r in releases} - with_jar
    words = complete_install("")
    assert words[:2] == ["stable", "rolling"]
    assert set(words) == {"stable", "rolling", *with_jar}
    assert not without_jar & set(words)
    assert len(words) == len(set(words))
    assert complete_install("v1.7") == [tag for tag in words if tag.startswith("v1.7")]


def test_cached_tags_skips_what_is_not_a_release_list_or_not_readable(isolated: Isolated, tmp_path: Path) -> None:
    cache = isolated.paths.remote
    write_cache(cache, "https://api.github.com/repos/o/r/releases/tags/v1", {"x": 1}, datetime.now(UTC))
    cache.joinpath("garbage.json").write_text("{", encoding="utf-8")
    cache.joinpath("list.json").write_text("[1]", encoding="utf-8")
    assert cached_tags(cache) == []
    assert cached_tags(cache / "missing") == []


def test_module_gives_the_registered_names(isolated: Isolated) -> None:
    for name in ("Alpha", "Beta"):
        folder = isolated.paths.modules / name
        folder.mkdir(parents=True)
        module = RegisteredModule(name, folder, "2026-01-01T00:00:00Z", "src", None, None, None, ())
        write_record(folder, module)
    assert complete_module("") == ["Alpha", "Beta"]
    assert complete_module("Al") == ["Alpha"]


def test_module_with_no_or_an_empty_folder_gives_nothing(isolated: Isolated) -> None:
    assert complete_module("") == []
    isolated.paths.modules.mkdir(parents=True)
    assert complete_module("") == []


def test_config_key_gives_the_keys_of_the_schema(isolated: Isolated) -> None:
    words = complete_config_key("tlc.")
    assert words == [key for key in setting_keys() if key.startswith("tlc.")]
    assert words


@pytest.mark.parametrize("completer", PATH_COMPLETERS)
def test_a_failing_completer_gives_nothing_and_prints_nothing(
    completer: Callable[[str], list[str]], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TLAUP_HOME", "relative/path")  # AppPaths.from_env raises
    monkeypatch.setenv("TLAUP_DEBUG", "1")
    assert completer("") == []
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_spec_gives_tla_files_and_folders_that_start_with_the_text(
    isolated: Isolated, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("Spec.tla", "Other.tla", "notes.txt"):
        (isolated.work / name).write_text("", encoding="utf-8")
    (isolated.work / "spec").mkdir()
    (isolated.work / "spec" / "Inner.tla").write_text("", encoding="utf-8")
    monkeypatch.chdir(isolated.work)
    assert complete_spec("S") == ["Spec.tla", "spec/"]
    assert complete_spec("spec/I") == ["spec/Inner.tla"]
    assert complete_spec("n") == []
