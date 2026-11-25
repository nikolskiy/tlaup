"""Finding Java and remembering the version check (design 13 J2, J3, M3; inventory row J1)."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Literal

import pytest

from tlaup.errors import Failed, JavacNotFound, JavaNotFound, JavaTooOld, ToolStartError
from tlaup.java.locate import (
    JAVA_PATTERNS,
    JAVAC_PATTERN,
    VersionAnswer,
    ask_version,
    locate,
    parse_version,
    require_java,
    require_javac,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tests.fakes.control import Fakes

BINARY = b"\x7fELF not really a program\n"
JAVA_OUT = 'openjdk version "25.0.5" 2026-10-20\n'
NOT_FOUND_TEXT = "Unable to locate a Java Runtime.\n"

Name = Literal["java", "javac"]


def make_tool(folder: Path, name: str = "java", content: bytes = BINARY, *, executable: bool = True) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(content)
    path.chmod(0o755 if executable else 0o644)
    return path


def jdk(root: Path) -> Path:
    for name in ("java", "javac"):
        make_tool(root / "bin", name)
    return root


class Counter:
    """A stand-in for `ask_version` that counts its calls."""

    def __init__(self, text: str = JAVA_OUT, exit_code: int = 0) -> None:
        self.answer = VersionAnswer(text, exit_code)
        self.calls: list[Path] = []

    def __call__(self, tool: Path) -> VersionAnswer:
        self.calls.append(tool)
        return self.answer


def env_for(*path_folders: Path, java_home: Path | None = None) -> dict[str, str]:
    env = {"PATH": os.pathsep.join(str(p) for p in path_folders)}
    if java_home is not None:
        env["JAVA_HOME"] = str(java_home)
    return env


# ---- locate (J2) ------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["java", "javac"])
def test_java_home_wins_over_path(tmp_path: Path, name: Name) -> None:
    home = jdk(tmp_path / "home")
    make_tool(tmp_path / "other", name)
    result = locate(name, env_for(tmp_path / "other", java_home=home))
    assert result.tool is not None
    assert result.tool.source == "JAVA_HOME"
    assert result.tool.path == home / "bin" / name
    assert result.warning is None


@pytest.mark.parametrize("name", ["java", "javac"])
def test_empty_java_home_falls_back_to_path_with_a_warning(tmp_path: Path, name: Name) -> None:
    (tmp_path / "empty").mkdir()
    on_path = make_tool(tmp_path / "other", name)
    result = locate(name, env_for(tmp_path / "other", java_home=tmp_path / "empty"))
    assert result.tool is not None
    assert result.tool.source == "PATH"
    assert result.tool.path == on_path
    assert result.warning is not None
    assert "JAVA_HOME" in result.warning


@pytest.mark.parametrize("name", ["java", "javac"])
def test_neither_gives_no_tool(tmp_path: Path, name: Name) -> None:
    assert locate(name, env_for(tmp_path)).tool is None
    assert locate(name, {}).tool is None


@pytest.mark.skipif(os.name == "nt", reason="execute bits")
@pytest.mark.parametrize("name", ["java", "javac"])
def test_a_file_without_the_execute_bit_is_not_found(tmp_path: Path, name: Name) -> None:
    make_tool(tmp_path / "home" / "bin", name, executable=False)
    make_tool(tmp_path / "other", name, executable=False)
    assert locate(name, env_for(tmp_path / "other")).tool is None
    result = locate(name, env_for(tmp_path / "other", java_home=tmp_path / "home"))
    assert result.tool is None
    assert result.warning is not None


def test_locate_reads_the_given_env_not_the_process(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    make_tool(tmp_path / "other", "java")
    monkeypatch.setenv("PATH", str(tmp_path / "other"))
    assert locate("java", {}).tool is None


def test_locate_prints_nothing(tmp_path: Path, capfd: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "empty").mkdir()
    locate("java", env_for(tmp_path, java_home=tmp_path / "empty"))
    locate("javac", {})
    captured = capfd.readouterr()
    assert captured.out == ""
    assert captured.err == ""


# ---- remembering (J3) ---------------------------------------------------------------------------


def test_a_plain_binary_is_asked_once(tmp_path: Path) -> None:
    make_tool(tmp_path / "bin")
    asked = Counter()
    env, cache = env_for(tmp_path / "bin"), tmp_path / "cache" / "java.json"
    first = require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    second = require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    assert len(asked.calls) == 1
    assert (first.version, first.major) == ("25.0.5", 25)
    assert (second.version, second.major) == ("25.0.5", 25)
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert data["schema"] == 1
    (entry,) = data["entries"].values()
    assert entry["version"] == "25.0.5"
    assert entry["major"] == 25


def test_a_changed_size_asks_again(tmp_path: Path) -> None:
    java = make_tool(tmp_path / "bin")
    asked = Counter()
    env, cache = env_for(tmp_path / "bin"), tmp_path / "java.json"
    require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    java.write_bytes(BINARY + b"more")
    require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    assert len(asked.calls) == 2


def test_a_changed_modification_time_asks_again(tmp_path: Path) -> None:
    java = make_tool(tmp_path / "bin")
    asked = Counter()
    env, cache = env_for(tmp_path / "bin"), tmp_path / "java.json"
    require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    now = java.stat().st_mtime_ns
    os.utime(java, ns=(now + 5_000_000_000, now + 5_000_000_000))
    require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    assert len(asked.calls) == 2


def test_a_script_named_java_is_asked_every_time(tmp_path: Path) -> None:
    make_tool(tmp_path / "bin", content=b'#!/bin/sh\nexec real-java "$@"\n')
    asked = Counter()
    env, cache = env_for(tmp_path / "bin"), tmp_path / "java.json"
    require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    assert len(asked.calls) == 2
    assert not cache.exists()


@pytest.mark.skipif(os.name == "nt", reason="links")
def test_a_link_named_java_to_another_name_is_asked_every_time(tmp_path: Path) -> None:
    manager = make_tool(tmp_path / "manager", "version-manager")
    (tmp_path / "jbin").mkdir()
    (tmp_path / "jbin" / "java").symlink_to(manager)
    asked = Counter()
    env, cache = env_for(tmp_path / "jbin"), tmp_path / "java.json"
    require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    assert len(asked.calls) == 2


@pytest.mark.parametrize("junk", ["not json", "[1, 2]", '{"schema": 2, "entries": {}}', '{"schema": 1, "entries": 5}'])
def test_an_unreadable_or_foreign_cache_is_ignored_and_rewritten(tmp_path: Path, junk: str) -> None:
    make_tool(tmp_path / "bin")
    cache = tmp_path / "java.json"
    cache.write_text(junk, encoding="utf-8")
    asked = Counter()
    env = env_for(tmp_path / "bin")
    require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    require_java(env, min_version=11, cache_file=cache, ask_version=asked)
    assert len(asked.calls) == 1
    assert json.loads(cache.read_text(encoding="utf-8"))["schema"] == 1


def test_java_and_javac_share_one_file(tmp_path: Path) -> None:
    jdk(tmp_path)
    env, cache = env_for(tmp_path / "bin"), tmp_path / "java.json"
    require_java(env, min_version=11, cache_file=cache, ask_version=Counter())
    require_javac(env, min_version=11, cache_file=cache, ask_version=Counter("javac 25.0.5\n"))
    assert len(json.loads(cache.read_text(encoding="utf-8"))["entries"]) == 2


def test_refresh_asks_again_and_rewrites_the_entry(tmp_path: Path) -> None:
    make_tool(tmp_path / "bin")
    cache = tmp_path / "java.json"
    env = env_for(tmp_path / "bin")
    require_java(env, min_version=11, cache_file=cache, ask_version=Counter())
    asked = Counter('openjdk version "17.0.1" 2021-10-19\n')
    runtime = require_java(env, min_version=11, cache_file=cache, ask_version=asked, refresh=True)
    assert len(asked.calls) == 1
    assert runtime.major == 17
    (entry,) = json.loads(cache.read_text(encoding="utf-8"))["entries"].values()
    assert entry["version"] == "17.0.1"
    # and a later call reads the new entry
    later = Counter()
    assert require_java(env, min_version=11, cache_file=cache, ask_version=later).major == 17
    assert later.calls == []


# ---- macOS rules, reported from Linux ---------------------------------------------------------


def test_macos_usr_bin_java_and_javac_are_asked_every_time(tmp_path: Path) -> None:
    usr_bin = tmp_path / "usr" / "bin"
    for name, require in (("java", require_java), ("javac", require_javac)):
        make_tool(usr_bin, name)
        asked = Counter(JAVA_OUT if name == "java" else "javac 25.0.5\n")
        for _ in range(2):
            require(
                env_for(usr_bin),
                min_version=11,
                cache_file=tmp_path / "java.json",
                ask_version=asked,
                platform="darwin",
                usr_bin=usr_bin,
            )
        assert len(asked.calls) == 2, name


def test_the_same_folder_is_remembered_on_linux(tmp_path: Path) -> None:
    usr_bin = tmp_path / "usr" / "bin"
    make_tool(usr_bin)
    asked = Counter()
    for _ in range(2):
        require_java(
            env_for(usr_bin),
            min_version=11,
            cache_file=tmp_path / "java.json",
            ask_version=asked,
            platform="linux",
            usr_bin=usr_bin,
        )
    assert len(asked.calls) == 1


@pytest.mark.skipif(os.name == "nt", reason="hard links")
def test_macos_the_same_file_as_java_home_is_asked_every_time(tmp_path: Path) -> None:
    stub = make_tool(tmp_path / "libexec", "java_home")
    (tmp_path / "jbin").mkdir()
    os.link(stub, tmp_path / "jbin" / "java")
    asked = Counter()
    for _ in range(2):
        require_java(
            env_for(tmp_path / "jbin"),
            min_version=11,
            cache_file=tmp_path / "java.json",
            ask_version=asked,
            platform="darwin",
            usr_bin=tmp_path / "nowhere",
            java_home_stub=stub,
        )
    assert len(asked.calls) == 2


# ---- ask_version and the failures told apart --------------------------------------------------


@pytest.mark.skipif(os.name == "nt", reason="launchers are scripts run by the interpreter")
def test_ask_version_reads_stderr_and_the_exit_status(fakes: Fakes) -> None:
    fakes.script("java", {"version": "11.0.2"})
    answer = ask_version(fakes.bin / "java")
    assert answer.exit_code == 0
    assert 'version "11.0.2"' in answer.text


@pytest.mark.skipif(os.name == "nt", reason="launchers are scripts run by the interpreter")
def test_ask_version_timeout_is_a_timeout_not_a_missing_java(fakes: Fakes) -> None:
    fakes.script("java", {"version_delay_ms": 60000})
    with pytest.raises(Failed) as caught:
        ask_version(fakes.bin / "java", timeout=0.5)
    assert type(caught.value) is Failed
    assert "seconds" in caught.value.message
    assert "not found" not in caught.value.message


def test_ask_version_on_random_bytes_is_a_start_error(tmp_path: Path) -> None:
    path = tmp_path / "java"
    path.write_bytes(os.urandom(256))
    path.chmod(0o755)
    with pytest.raises(ToolStartError) as caught:
        ask_version(path)
    assert str(path) in caught.value.message


def test_a_non_zero_answer_without_a_version_is_java_not_found(tmp_path: Path) -> None:
    make_tool(tmp_path / "bin")
    with pytest.raises(JavaNotFound) as caught:
        require_java(
            env_for(tmp_path / "bin"),
            min_version=11,
            cache_file=tmp_path / "java.json",
            ask_version=Counter(NOT_FOUND_TEXT, exit_code=1),
        )
    assert caught.value.exit_code == 3
    assert caught.value.details is not None
    assert "Unable to locate a Java Runtime." in caught.value.details
    assert caught.value.hint == "install Java 11 or newer"


def test_nothing_found_is_java_not_found_with_the_words_of_the_design(tmp_path: Path) -> None:
    with pytest.raises(JavaNotFound) as caught:
        require_java({}, min_version=11, cache_file=tmp_path / "java.json", ask_version=Counter())
    assert caught.value.message == "Java was not found (looked in JAVA_HOME and PATH)"
    assert caught.value.hint == "install Java 11 or newer"


def test_an_answer_that_is_not_a_version_is_a_warning(tmp_path: Path) -> None:
    make_tool(tmp_path / "bin")
    cache = tmp_path / "java.json"
    runtime = require_java(
        env_for(tmp_path / "bin"),
        min_version=11,
        cache_file=cache,
        ask_version=Counter("hello from a strange java\n"),
    )
    assert runtime.version is None
    assert runtime.major is None
    assert len(runtime.warnings) == 1
    assert "hello from a strange java" in runtime.warnings[0]
    assert not cache.exists()


def test_a_version_below_the_minimum_is_too_old(tmp_path: Path) -> None:
    make_tool(tmp_path / "bin")
    with pytest.raises(JavaTooOld) as caught:
        require_java(
            env_for(tmp_path / "bin"),
            min_version=11,
            cache_file=tmp_path / "java.json",
            ask_version=Counter('java version "1.8.0_202"\n'),
        )
    assert caught.value.exit_code == 3
    assert "11 or newer is needed" in caught.value.message
    assert "version 8" in caught.value.message


def test_too_old_through_java_home_says_so(tmp_path: Path) -> None:
    home = jdk(tmp_path / "home")
    with pytest.raises(JavaTooOld) as caught:
        require_java(
            env_for(java_home=home),
            min_version=11,
            cache_file=tmp_path / "java.json",
            ask_version=Counter('java version "1.8.0_202"\n'),
        )
    assert "JAVA_HOME" in caught.value.message
    assert str(home / "bin" / "java") in caught.value.message


def test_a_stale_java_home_warning_travels_in_the_runtime(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    make_tool(tmp_path / "bin")
    runtime = require_java(
        env_for(tmp_path / "bin", java_home=tmp_path / "empty"),
        min_version=11,
        cache_file=tmp_path / "java.json",
        ask_version=Counter(),
    )
    assert len(runtime.warnings) == 1
    assert "JAVA_HOME" in runtime.warnings[0]


# ---- the patterns (row J1) --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "major"),
    [
        ('java version "1.8.0_202"', 8),
        ('openjdk version "11.0.2" 2019-01-15', 11),
        ('openjdk version "17"', 17),
        ('openjdk version "21.0.1" 2023-10-17', 21),
        ("openjdk version 21", 21),
        ('openjdk version "9.0.4"', 9),
    ],
)
def test_java_patterns(text: str, major: int) -> None:
    parsed = parse_version(text, "java")
    assert parsed is not None
    assert parsed[1] == major


def test_java_pattern_keeps_the_version_string() -> None:
    assert parse_version('openjdk version "11.0.2" 2019-01-15', "java") == ("11.0.2", 11)
    assert parse_version('java version "1.8.0_202"', "java") == ("1.8.0_202", 8)


JAVAC_CASES = [
    ("javac 25.0.5", "25.0.5", 25),
    ("javac 11.0.2", "11.0.2", 11),
    ("javac 1.8.0_202", "1.8.0_202", 8),
    ("javac 17-ea", "17-ea", 17),
    ("Picked up JAVA_TOOL_OPTIONS: -Xmx1g\njavac 25.0.5\n", "25.0.5", 25),
]


@pytest.mark.parametrize(("text", "version", "major"), JAVAC_CASES)
def test_javac_pattern(text: str, version: str, major: int) -> None:
    assert parse_version(text, "javac") == (version, major)
    assert JAVAC_PATTERN.search(text) is not None
    assert not any(pattern.search(text) for pattern in JAVA_PATTERNS)


# ---- javac (M3) ---------------------------------------------------------------------------------


def test_an_old_javac_is_too_old_and_names_javac(tmp_path: Path) -> None:
    javac = make_tool(tmp_path / "bin", "javac")
    with pytest.raises(JavaTooOld) as caught:
        require_javac(
            env_for(tmp_path / "bin"),
            min_version=11,
            cache_file=tmp_path / "java.json",
            ask_version=Counter("javac 1.8.0_202\n"),
        )
    assert "javac" in caught.value.message
    assert str(javac) in caught.value.message


def test_no_javac_is_javac_not_found(tmp_path: Path) -> None:
    make_tool(tmp_path / "bin", "java")
    with pytest.raises(JavacNotFound) as caught:
        require_javac({"PATH": str(tmp_path / "bin")}, min_version=11, cache_file=tmp_path / "java.json")
    assert caught.value.exit_code == 3
    assert "javac was not found" in caught.value.message


def test_javac_answer_not_a_version_goes_on(tmp_path: Path) -> None:
    make_tool(tmp_path / "bin", "javac")
    runtime = require_javac(
        env_for(tmp_path / "bin"),
        min_version=11,
        cache_file=tmp_path / "java.json",
        ask_version=Counter("something else\n"),
    )
    assert runtime.version is None
    assert len(runtime.warnings) == 1
