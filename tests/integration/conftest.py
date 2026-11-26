"""The integration tests' harness: real Java and real jars (design 01 T9, T2; package 52).

At collection, before any fixture runs: every test here is skipped with the reason when ``TLAUP_TEST_JARS`` is unset
or names no jar, or when no ``java`` is found (``JAVA_HOME``, then ``PATH``); a jar that matches no golden folder
fails collection, naming it. Every item here is marked ``integration``. The ``isolated`` fixture replaces the root
one for this folder: the real ``PATH`` and ``JAVA_HOME`` stay, and the JVM's own folders move too. ``live_build``
copies one of the found jars into the test's store and pins it; every test that asks for it runs once per jar.
"""

from __future__ import annotations

import os
import shlex
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import tlaup.context
from tests.integration.discovery import VARIABLE, TestJar, find_test_jars, install, missing
from tlaup.paths import AppPaths

if TYPE_CHECKING:
    from tlaup.versioning.store import Build


def _discover() -> tuple[str | None, list[TestJar], str | None]:
    """At collection (this conftest is imported then): why the folder is skipped, the jars, a jar matching nothing."""
    reason = missing(os.environ)
    if reason is not None:
        return reason, [], None
    try:
        return None, find_test_jars(Path(os.environ[VARIABLE])), None
    except ValueError as error:
        return None, [], str(error)


# Read once, before any fixture runs: the isolation fixture removes every TLAUP_* variable.
_REASON, JARS, _NO_MATCH = _discover()


# Removed before every test, besides every TLAUP_* variable: the root fixture's list without JAVA_HOME (T2).
_REMOVED = (
    "JAVA_OPTS",
    "JDK_JAVA_OPTIONS",
    "JAVA_TOOL_OPTIONS",
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "EDITOR",
    "VISUAL",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
    "XDG_DATA_HOME",
    "FORCE_COLOR",
    "CLICOLOR_FORCE",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Every item here is marked ``integration``, and skipped with the reason when the tests cannot run (T9).

    ``pytest.skip(allow_module_level=True)`` at the top of this file would be the shorter form, but pytest 9 stops
    with an internal error when the conftest of a folder named on the command line raises it, so the skip is a
    marker on every item, put first so that its reason is the one shown.
    """
    if _NO_MATCH is not None:
        raise pytest.UsageError(_NO_MATCH)
    here = Path(__file__).parent
    for item in items:
        if here in Path(str(item.path)).parents:
            item.add_marker(pytest.mark.integration)
            if _REASON is not None:
                reason = f"integration tests skipped: {_REASON} (see docs/contributing/development.md)"
                item.add_marker(pytest.mark.skip(reason=reason), append=False)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """``test_jar`` (and so ``live_build``) once per jar found, with the build's name as the id; ``live_case``
    once per jar and per case the test module's ``live_cases`` gives for the jar's golden folder."""
    if "live_case" in metafunc.fixturenames:
        pairs = [(jar, case) for jar in JARS for case in metafunc.module.live_cases(jar.golden)]
        metafunc.parametrize("live_case", pairs, ids=[f"{jar.build}/{case}" for jar, case in pairs])
    elif "test_jar" in metafunc.fixturenames:
        metafunc.parametrize("test_jar", JARS, ids=[jar.build for jar in JARS])


@dataclass(frozen=True)
class Isolated:
    home: Path  # tmp_path / "home"; HOME and USERPROFILE
    work: Path  # tmp_path / "work"; the working folder, created
    paths: AppPaths  # AppPaths.from_env(os.environ) after the fixture's changes
    tmp: Path  # tmp_path / "jvm" / "tmp"; the JVM's java.io.tmpdir
    user_home: Path  # tmp_path / "jvm" / "home"; the JVM's user.home, apart from HOME so a test can tell them apart


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Isolated:
    """The root fixture's isolation, with the real PATH and JAVA_HOME and the JVM's own folders moved (T2, T9)."""
    home = tmp_path / "home"
    work = tmp_path / "work"
    jvm_tmp = tmp_path / "jvm" / "tmp"
    user_home = tmp_path / "jvm" / "home"
    for folder in (home, work, jvm_tmp, user_home):
        folder.mkdir(parents=True)
    for name in list(os.environ):
        if name.startswith("TLAUP_"):
            monkeypatch.delenv(name)
    for name in _REMOVED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TLAUP_HOME", str(home / "tlaup"))  # moves config, cache and data (D25)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("TZ", "UTC")
    if hasattr(time, "tzset"):
        time.tzset()
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("COLUMNS", "100")
    monkeypatch.setenv("LINES", "40")
    # The JVM takes user.home from the system, not from HOME; TLC and SANY write into java.io.tmpdir (T9, 13 J1).
    options = [f"-Duser.home={user_home}", f"-Djava.io.tmpdir={jvm_tmp}"]
    monkeypatch.setenv("TLAUP_JAVA_OPTS", shlex.join(options))
    monkeypatch.setenv(
        "TLAUP_TOOL_REPOSITORY",  # a closed local port: no test uses the network (T4, Network)
        "https://127.0.0.1:9/repos/tlaplus/tlaplus",
    )
    monkeypatch.chdir(work)
    tlaup.context.reset()  # the one process-wide cache
    return Isolated(home=home, work=work, paths=AppPaths.from_env(os.environ), tmp=jvm_tmp, user_home=user_home)


@pytest.fixture
def test_jar(request: pytest.FixtureRequest) -> TestJar:
    """One of the jars found under TLAUP_TEST_JARS (parametrised by ``pytest_generate_tests``)."""
    jar: TestJar = request.param
    return jar


@pytest.fixture
def live_build(test_jar: TestJar, isolated: Isolated) -> Build:
    """``test_jar`` copied into the test's store and pinned (12 V1); no network."""
    return install(isolated.paths, test_jar)
