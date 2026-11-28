"""scripts/prepare_release.py on changelogs the test writes, with the bump replaced (design 30 L8)."""

from __future__ import annotations

import datetime
import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

SCRIPT = Path(__file__).parents[3] / "scripts" / "prepare_release.py"

CHANGELOG = """# Changelog

Words about the format.

## [Unreleased]

### Added

- A thing.

## [0.8.2] - 2026-11-14

### Fixed

- An old thing.
"""


@pytest.fixture
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("prepare_release_script", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _never(part: str) -> str:
    message = f"the bump ran ({part}) although the release was refused"
    raise AssertionError(message)


def test_the_entries_move_under_the_dated_version_and_unreleased_stays_empty(script: ModuleType) -> None:
    result = script.date_changelog(CHANGELOG, "0.9.0", datetime.date(2026, 11, 28))
    assert "## [Unreleased]\n\n## [0.9.0] - 2026-11-28\n\n### Added\n\n- A thing.\n\n## [0.8.2]" in result
    assert result.startswith("# Changelog\n\nWords about the format.\n\n")
    assert result.endswith("- An old thing.\n")


def test_main_bumps_dates_and_prints_only_the_version(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    parts: list[str] = []

    def bump(part: str) -> str:
        parts.append(part)
        return "0.9.0"

    code = script.main(["minor", "--date", "2026-12-01"], changelog=changelog, bumper=bump)
    assert code == 0
    assert parts == ["minor"]
    assert capsys.readouterr().out == "0.9.0\n"
    assert "## [0.9.0] - 2026-12-01" in changelog.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("text", "says"),
    [
        (CHANGELOG.replace("### Added\n\n- A thing.\n\n", ""), "nothing to release"),
        (CHANGELOG.replace("## [Unreleased]\n\n", ""), "has no ## [Unreleased]"),
        (CHANGELOG + "\n## [Unreleased]\n\n- Again.\n", "has 2 ## [Unreleased]"),
    ],
    ids=["empty", "missing", "twice"],
)
def test_a_changelog_without_one_unreleased_section_with_entries_is_refused_before_the_bump(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str, says: str
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(text, encoding="utf-8")
    assert script.main(["patch"], changelog=changelog, bumper=_never) == 1
    assert says in capsys.readouterr().err
    assert changelog.read_text(encoding="utf-8") == text


def test_a_version_the_changelog_already_has_is_refused(script: ModuleType) -> None:
    with pytest.raises(script.PrepareError, match="appears 2 times"):
        script.date_changelog(CHANGELOG, "0.8.2", datetime.date(2026, 11, 28))


@pytest.mark.parametrize(
    "argv",
    [[], ["minor", "extra"], ["huge"], ["minor", "--date", "tomorrow"], ["minor", "--date"]],
    ids=["none", "extra", "unknown-part", "bad-date", "date-missing"],
)
def test_bad_arguments_are_refused(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str], argv: list[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")
    assert script.main(argv, changelog=changelog, bumper=_never) == 2
    assert capsys.readouterr().err
    assert changelog.read_text(encoding="utf-8") == CHANGELOG


def test_a_failed_bump_leaves_the_changelog_alone(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(CHANGELOG, encoding="utf-8")

    def fail(part: str) -> str:
        message = f"uv version --bump {part} failed (exit 2)."
        raise script.PrepareError(message)

    assert script.main(["patch"], changelog=changelog, bumper=fail) == 1
    assert "failed (exit 2)" in capsys.readouterr().err
    assert changelog.read_text(encoding="utf-8") == CHANGELOG


def test_a_missing_changelog_is_an_error(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert script.main(["patch"], changelog=tmp_path / "CHANGELOG.md", bumper=_never) == 1
    assert "Cannot read or write" in capsys.readouterr().err
