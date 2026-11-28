"""scripts/release_check.py on trees the test writes, with PyPI replaced (design 30 L8)."""

from __future__ import annotations

import importlib.util
import io
import urllib.error
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

SCRIPT = Path(__file__).parents[3] / "scripts" / "release_check.py"

TAGS = "aaa1\trefs/tags/v0.8.1\nbbb2\trefs/tags/v0.8.2\nccc3\trefs/tags/not-a-version\nddd4\trefs/tags/v1.0\n"

RELEASED = """# Changelog

## [Unreleased]

### Added

- Waiting for a release.

## [0.8.2] - 2026-11-14

- Old.
"""

READY = """# Changelog

## [Unreleased]

## [0.9.0] - 2026-11-28

### Added

- New.

## [0.8.2] - 2026-11-14

- Old.
"""


@pytest.fixture
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_check_script", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tree(root: Path, version: str, changelog: str, locked: str | None = None) -> Path:
    (root / "pyproject.toml").write_text(f'[project]\nname = "tlaup"\nversion = "{version}"\n', encoding="utf-8")
    lock_version = version if locked is None else locked
    (root / "uv.lock").write_text(
        f'version = 1\n\n[[package]]\nname = "other"\nversion = "9.9.9"\n\n'
        f'[[package]]\nname = "tlaup"\nversion = "{lock_version}"\n',
        encoding="utf-8",
    )
    (root / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    (root / "tags.txt").write_text(TAGS, encoding="utf-8")
    return root


def pypi(answer: bool) -> object:
    asked: list[str] = []

    def has(version: str) -> bool:
        asked.append(version)
        return answer

    has.asked = asked  # type: ignore[attr-defined]
    return has


def run(script: ModuleType, root: Path, mode: str, on_pypi: object) -> int:
    return script.main(["--tags", str(root / "tags.txt"), "--mode", mode], root=root, on_pypi=on_pypi)


def test_only_version_tags_count(script: ModuleType) -> None:
    assert script.parse_tags(TAGS) == {(0, 8, 1), (0, 8, 2)}


@pytest.mark.parametrize("mode", ["pr", "publish"])
def test_a_tagged_version_is_not_a_release_and_pypi_is_not_asked(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    mode: str,
) -> None:
    output = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    root = tree(tmp_path, "0.8.2", RELEASED)
    has = pypi(answer=True)
    assert run(script, root, mode, has) == 0
    assert has.asked == []  # type: ignore[attr-defined]
    assert "not a release" in capsys.readouterr().out
    assert output.read_text(encoding="utf-8") == "release=false\nversion=0.8.2\n"


def test_a_ready_release_passes_and_says_so(
    script: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    root = tree(tmp_path, "0.9.0", READY)
    has = pypi(answer=False)
    assert run(script, root, "publish", has) == 0
    assert has.asked == ["0.9.0"]  # type: ignore[attr-defined]
    assert "every release check passed" in capsys.readouterr().out
    assert output.read_text(encoding="utf-8") == "release=true\nversion=0.9.0\n"


@pytest.mark.parametrize(
    ("version", "changelog", "locked", "says"),
    [
        ("0.8.0", RELEASED, None, "not higher than the latest tag v0.8.2"),
        ("0.9.0", READY, "0.8.2", "uv.lock has tlaup 0.8.2"),
        ("0.9.0", RELEASED, None, "## [Unreleased] still has entries"),
        ("0.9.0", READY.replace("## [0.9.0] - 2026-11-28", "## [0.9.0]"), None, "malformed"),
    ],
    ids=["not-higher", "lock-differs", "unreleased-entries", "undated"],
)
def test_an_unready_release_fails_and_writes_no_outputs(
    script: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    version: str,
    changelog: str,
    locked: str | None,
    says: str,
) -> None:
    output = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    root = tree(tmp_path, version, changelog, locked)
    assert run(script, root, "pr", pypi(answer=False)) == 1
    err = capsys.readouterr().err
    assert "not releasable" in err
    assert says in err
    assert not output.exists()


@pytest.mark.parametrize(
    ("mode", "says"),
    [("pr", "cannot be uploaded twice"), ("publish", "Re-run the failed jobs of that run")],
)
def test_an_untagged_version_already_on_pypi_fails_with_the_way_out_for_its_mode(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str, says: str
) -> None:
    root = tree(tmp_path, "0.9.0", READY)
    assert run(script, root, mode, pypi(answer=True)) == 1
    assert says in capsys.readouterr().err


def test_a_lock_without_tlaup_is_a_problem(script: ModuleType, tmp_path: Path) -> None:
    root = tree(tmp_path, "0.9.0", READY)
    (root / "uv.lock").write_text('version = 1\n\n[[package]]\nname = "other"\nversion = "1.0.0"\n', encoding="utf-8")
    verdict = script.evaluate(root, {(0, 8, 2)}, "pr", pypi(answer=False))
    assert verdict.problems == ["uv.lock has tlaup <none>, pyproject.toml has 0.9.0; run uv lock."]


def test_no_tags_at_all_needs_no_ordering(script: ModuleType, tmp_path: Path) -> None:
    root = tree(tmp_path, "0.9.0", READY)
    verdict = script.evaluate(root, set(), "pr", pypi(answer=False))
    assert verdict.release
    assert verdict.problems == []


@pytest.mark.parametrize(
    "argv",
    [[], ["--tags"], ["--mode", "pr"], ["--tags", "t", "--mode", "release"], ["--tags", "t", "--other", "x"]],
    ids=["none", "no-value", "no-tags", "bad-mode", "unknown-option"],
)
def test_bad_arguments_are_refused(script: ModuleType, capsys: pytest.CaptureFixture[str], argv: list[str]) -> None:
    assert script.main(argv) == 2
    assert "usage" in capsys.readouterr().err


def test_unreadable_facts_are_errors_not_passes(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tree(tmp_path, "0.9.0", READY)
    assert script.main(["--tags", str(tmp_path / "missing.txt")], root=root, on_pypi=pypi(answer=False)) == 1
    assert "cannot read" in capsys.readouterr().err
    (root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert run(script, root, "pr", pypi(answer=False)) == 1
    assert "no [project] version" in capsys.readouterr().err
    (root / "pyproject.toml").write_text('[project]\nversion = "nine"\n', encoding="utf-8")
    assert run(script, root, "pr", pypi(answer=False)) == 1
    assert "not of the form X.Y.Z" in capsys.readouterr().err


class _Response:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


@pytest.mark.parametrize(("status", "expected"), [(200, True), (404, False)])
def test_pypi_200_is_yes_and_404_is_no(script: ModuleType, status: int, *, expected: bool) -> None:
    def urlopen(url: str, timeout: float) -> _Response:
        assert url == "https://pypi.org/pypi/tlaup/0.9.0/json"
        assert timeout > 0
        if status == 404:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO())  # type: ignore[arg-type]
        return _Response(status)

    assert script.pypi_has("0.9.0", urlopen) is expected


@pytest.mark.parametrize(
    "failure",
    [
        urllib.error.HTTPError("u", 503, "Unavailable", {}, io.BytesIO()),  # type: ignore[arg-type]
        urllib.error.URLError("no network"),
        TimeoutError("slow"),
    ],
    ids=["503", "no-network", "timeout"],
)
def test_any_other_pypi_answer_is_an_error(script: ModuleType, failure: Exception) -> None:
    def urlopen(url: str, timeout: float) -> _Response:
        raise failure

    with pytest.raises(script.CheckError):
        script.pypi_has("0.9.0", urlopen)


def test_an_answer_other_than_200_without_an_error_is_an_error(script: ModuleType) -> None:
    with pytest.raises(script.CheckError, match="neither 200 nor 404"):
        script.pypi_has("0.9.0", lambda *_args, **_kwargs: _Response(204))
