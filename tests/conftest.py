"""Isolation, the fakes, the expected-file option and the Hypothesis profiles (design 01 T2, T4, T7, T8)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
import responses
from hypothesis import HealthCheck, settings

import tlaup.context
from tests import expected
from tests.fakes.control import Fakes, fake_bin_dir
from tests.github import GitHubFake
from tests.steps._scenario import Scenario
from tlaup.paths import AppPaths

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

# The step vocabulary of the feature files (design 01 T5), visible to tests/test_features.py's scenarios.
pytest_plugins = ["tests.steps.given", "tests.steps.when", "tests.steps.then"]

# Fixed and reproducible in CI; no example database (T7).
_QUIET = [HealthCheck.too_slow, HealthCheck.filter_too_much]
_COMMON = {"deadline": None, "suppress_health_check": _QUIET, "database": None}
settings.register_profile("ci", derandomize=True, max_examples=200, **_COMMON)
settings.register_profile("dev", max_examples=50, **_COMMON)
settings.load_profile("ci" if os.environ.get("CI") else "dev")

# Removed before every test, besides every TLAUP_* variable (T2).
_REMOVED = (
    "JAVA_HOME",
    "JAVA_OPTS",
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


@dataclass(frozen=True)
class Isolated:
    home: Path  # tmp_path / "home"; HOME and USERPROFILE
    work: Path  # tmp_path / "work"; the working folder, created
    bin: Path  # tmp_path / "bin"; the whole PATH: the four launchers
    paths: AppPaths  # AppPaths.from_env(os.environ) after the fixture's changes


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Isolated:
    """Every test's folders, home, working folder, terminal and PATH are temporary and fixed (T2)."""
    home = tmp_path / "home"
    work = tmp_path / "work"
    home.mkdir()
    work.mkdir()
    for name in list(os.environ):
        if name.startswith("TLAUP_"):
            monkeypatch.delenv(name)
    for name in _REMOVED:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TLAUP_HOME", str(home / "tlaup"))  # moves config, cache and data (D25)
    monkeypatch.setenv("HOME", str(home))  # anything that still asks for the home folder
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("COLUMNS", "100")
    monkeypatch.setenv("LINES", "40")
    bin_dir = fake_bin_dir(tmp_path)
    monkeypatch.setenv("PATH", str(bin_dir))  # only the fakes (T4)
    monkeypatch.setenv(
        "TLAUP_TOOL_REPOSITORY",  # a closed local port: a request that is not
        "https://127.0.0.1:9/repos/tlaplus/tlaplus",
    )  # recorded fails at once (T4, Network)
    monkeypatch.chdir(work)
    tlaup.context.reset()  # the one process-wide cache
    return Isolated(home=home, work=work, bin=bin_dir, paths=AppPaths.from_env(os.environ))


@pytest.fixture
def fakes(isolated: Isolated, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Fakes:
    """The four fake launchers on PATH, unscripted (T4)."""
    return Fakes(isolated.bin, tmp_path, monkeypatch)


@pytest.fixture
def scenario(
    isolated: Isolated, fakes: Fakes, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Scenario:
    """The state one feature scenario carries between its steps (T5, package 18)."""
    return Scenario(isolated, fakes, request, monkeypatch, tmp_path)


@pytest.fixture
def github(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Callable[..., GitHubFake]]:
    """``github(recording="releases")``: a recording served as GitHub's answers, at the default host (T4)."""
    monkeypatch.delenv("TLAUP_TOOL_REPOSITORY", raising=False)
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:

        def start(recording: str = "releases") -> GitHubFake:
            return GitHubFake(mock, tmp_path, recording)

        yield start


def pytest_addoption(parser: pytest.Parser) -> None:
    expected.add_option(parser)


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter, config: pytest.Config) -> None:
    expected.report_written(terminalreporter, config)
