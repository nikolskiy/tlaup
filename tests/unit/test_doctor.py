"""The checks of `tlaup doctor` on real files in a temporary `AppPaths` (design 23 C1, 13 J3; package 46)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.clock import FakeClock
from tests.unit.versioning.conftest import Downloads, commit, manifest
from tlaup.doctor import Check, run_checks
from tlaup.errors import Failed
from tlaup.java.locate import VersionAnswer, require_java
from tlaup.modules.registry import RegisteredModule, write_record
from tlaup.paths import AppPaths
from tlaup.versioning.store import ToolStore

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tests.conftest import Isolated

BANNER = 'openjdk version "25.0.5" 2026-10-20\n'
JAVAC_BANNER = "javac 25.0.5\n"
NAMES = [
    "java",
    "javac",
    "pinned build",
    "tool folder",
    "config file",
    "module folder",
    "config folder",
    "cache folder",
    "data folder",
    "run folder",
    "GitHub token",
]
ON_POSIX = os.name != "nt"
NOT_ROOT = not hasattr(os, "geteuid") or os.geteuid() != 0


class Asker:
    """A stand-in for `ask_version` that counts its calls and answers as `java` or `javac`."""

    def __init__(self) -> None:
        self.calls: list[Path] = []

    def __call__(self, tool: Path) -> VersionAnswer:
        self.calls.append(tool)
        return VersionAnswer(JAVAC_BANNER if tool.stem == "javac" else BANNER, 0)


def make_binary(folder: Path, name: str) -> Path:
    """A file that is not a `#!` script, so the check is remembered (J3)."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(b"\x7fELF not really a program\n")
    path.chmod(0o755)
    return path


def env_with_java(isolated: Isolated, *, javac: bool = True) -> dict[str, str]:
    folder = isolated.home / "jdk" / "bin"
    make_binary(folder, "java")
    if javac:
        make_binary(folder, "javac")
    return {"PATH": str(folder)}


def by_name(checks: list[Check]) -> dict[str, Check]:
    return {check.name: check for check in checks}


@pytest.fixture
def store(isolated: Isolated) -> ToolStore:
    return ToolStore(isolated.paths, now=FakeClock().now)


@pytest.fixture
def downloads(store: ToolStore) -> Iterator[Downloads]:
    made = Downloads(store)
    yield made
    made.release()


@pytest.fixture
def pinned(isolated: Isolated, downloads: Downloads, store: ToolStore) -> Path:
    build = downloads.add(manifest(commit("5a47802"), "2026-11-15T00:21:46Z"), "v1.7.4", prerelease=False)
    with store.locked(timeout=0):
        store.pin(build)
    return build.jar


# ---------------------------------------------------------------------- the re-run (J3, Risks)


@pytest.mark.skipif(not ON_POSIX, reason="a plain binary named java is a POSIX file here")
def test_require_java_asks_once_but_doctor_asks_every_time(isolated: Isolated) -> None:
    env = env_with_java(isolated)
    cache = isolated.paths.java_cache
    counting = Asker()
    for _ in range(2):
        require_java(env, min_version=11, cache_file=cache, ask_version=counting)
    assert len(counting.calls) == 1

    counting = Asker()
    for _ in range(2):
        run_checks(isolated.paths, env, ask_version=counting)
    assert [call.name for call in counting.calls] == ["java", "javac", "java", "javac"]
    entries = json.loads(cache.read_text(encoding="utf-8"))["entries"]
    assert {Path(key).name for key in entries} == {"java", "javac"}


@pytest.mark.skipif(not ON_POSIX, reason="a plain binary named java is a POSIX file here")
def test_only_the_cache_folder_is_made_and_it_holds_java_json_alone(tmp_path: Path, isolated: Isolated) -> None:
    base = tmp_path / "only-parent"
    base.mkdir()
    paths = AppPaths(config=base / "config", cache=base / "cache", data=base / "data")
    run_checks(paths, env_with_java(isolated), ask_version=Asker())
    assert sorted(entry.name for entry in base.iterdir()) == ["cache"]
    assert [entry.name for entry in paths.cache.iterdir()] == ["java.json"]


# ---------------------------------------------------------------------- ToolStore.leftovers


def test_leftovers_are_what_is_not_a_build_and_not_the_stores_own(
    isolated: Isolated, store: ToolStore, downloads: Downloads, pinned: Path
) -> None:
    tools = isolated.paths.tools
    (tools / "jar-only").mkdir()
    (tools / "jar-only" / "tla2tools.jar").write_bytes(b"x")
    (tools / "new-schema").mkdir()
    (tools / "new-schema" / "tla2tools.jar").write_bytes(b"x")
    (tools / "new-schema" / "build.json").write_text(json.dumps({"schema": 99}), encoding="utf-8")
    (tools / "stray-file").write_text("x", encoding="utf-8")
    (tools / ".lock").touch()
    (tools / ".tmp").mkdir(exist_ok=True)
    assert [entry.name for entry in store.leftovers()] == ["jar-only", "new-schema", "stray-file"]


def test_leftovers_of_a_missing_folder_is_empty(store: ToolStore) -> None:
    assert store.leftovers() == []


# ---------------------------------------------------------------------- the module folder (finding H1)


def module(isolated: Isolated, name: str) -> None:
    folder = isolated.paths.modules / name
    folder.mkdir(parents=True)
    write_record(
        folder,
        RegisteredModule(name, folder, "2026-11-15T00:00:00Z", "/src", None, None, None, ()),
    )


def test_a_broken_module_folder_is_one_warning_and_the_registrys_own_entries_are_not(isolated: Isolated) -> None:
    modules = isolated.paths.modules
    (modules / ".tmp" / "20261115T000000Z-ab12cd34").mkdir(parents=True)
    (modules / ".lock").touch()
    module(isolated, "Real")
    (modules / "broken").mkdir()
    (modules / "broken" / "module.json").write_text("not json", encoding="utf-8")
    check = by_name(run_checks(isolated.paths, {}, now=FakeClock().now))["module folder"]
    assert check.level == "warning"
    assert "broken" in check.detail
    assert "Real" not in check.detail
    assert ".tmp" not in check.detail
    assert ".lock" not in check.detail
    assert (modules / "broken" / "module.json").exists()

    (modules / "broken" / "module.json").unlink()
    (modules / "broken").rmdir()
    assert by_name(run_checks(isolated.paths, {}, now=FakeClock().now))["module folder"].level == "ok"


def test_a_stray_file_and_a_bad_name_in_the_module_folder_are_named(isolated: Isolated) -> None:
    modules = isolated.paths.modules
    modules.mkdir(parents=True)
    (modules / "notes.txt").write_text("x", encoding="utf-8")
    (modules / "bad name").mkdir()
    detail = by_name(run_checks(isolated.paths, {}, now=FakeClock().now))["module folder"].detail
    assert "notes.txt (not a module: a file)" in detail
    assert "bad name (not a valid module name)" in detail


# ---------------------------------------------------------------------- the pinned build


def test_a_jar_rewritten_with_other_bytes_of_the_same_length_is_an_error(isolated: Isolated, pinned: Path) -> None:
    assert by_name(run_checks(isolated.paths, {}))["pinned build"].level == "ok"
    data = pinned.read_bytes()
    pinned.write_bytes(bytes(byte ^ 1 for byte in data))
    check = by_name(run_checks(isolated.paths, {}))["pinned build"]
    assert check.level == "error"
    assert check.hint is not None
    assert "tlaup tool install --force v1.7.4" in check.hint


# ---------------------------------------------------------------------- all of them


@pytest.mark.skipif(not (ON_POSIX and NOT_ROOT), reason="permission bits do not bind root or Windows")
def test_run_checks_never_raises_and_gives_the_levels_of_the_table(isolated: Isolated) -> None:
    isolated.paths.config.mkdir(parents=True)
    isolated.paths.config_file.write_text("tlc: [unclosed\n", encoding="utf-8")
    isolated.paths.cache.mkdir(parents=True)
    isolated.paths.cache.chmod(0o500)
    try:
        checks = run_checks(isolated.paths, {"PATH": ""})
    finally:
        isolated.paths.cache.chmod(0o700)
    assert [check.name for check in checks] == NAMES
    levels = {check.name: check.level for check in checks}
    assert levels["java"] == "error"
    assert levels["javac"] == "warning"
    assert levels["pinned build"] == "error"
    assert levels["config file"] == "error"
    assert levels["cache folder"] == "error"
    assert levels["tool folder"] == "error"
    assert levels["run folder"] == "error"
    assert levels["config folder"] == "ok"
    assert levels["GitHub token"] == "ok"
    java = by_name(checks)["java"]
    assert "minimum 11" in java.detail
    assert "settings are invalid" in java.detail


def test_no_detail_or_hint_holds_the_tokens_value(isolated: Isolated, pinned: Path) -> None:
    secret = "doctor-secret-value"
    checks = run_checks(isolated.paths, {"GITHUB_TOKEN": secret, "PATH": ""})
    token = by_name(checks)["GitHub token"]
    assert token.level == "ok"
    assert "GITHUB_TOKEN" in token.detail
    assert not any(secret in f"{check.detail} {check.hint}" for check in checks)


def test_the_token_variable_named_is_the_one_used(isolated: Isolated) -> None:
    env = {"GH_TOKEN": "a", "GITHUB_TOKEN": "b", "PATH": ""}
    assert "GH_TOKEN" in by_name(run_checks(isolated.paths, env))["GitHub token"].detail


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_the_levels_of_the_folders(isolated: Isolated) -> None:
    checks = by_name(run_checks(isolated.paths, {"PATH": ""}))
    for name in ("config folder", "cache folder", "data folder", "run folder"):
        assert checks[name].level == "ok"
        assert "not there yet" in checks[name].detail


def test_a_version_check_that_fails_does_not_send_the_user_to_doctor(isolated: Isolated) -> None:
    env = env_with_java(isolated)

    def timing_out(tool: Path) -> VersionAnswer:
        message = f"{tool} -version did not answer within 10 seconds"
        raise Failed(message, hint="check that this Java starts, or run `tlaup doctor`")

    java = by_name(run_checks(isolated.paths, env, ask_version=timing_out))["java"]
    assert java.level == "error"
    assert java.hint == "check that this Java starts"
