"""scripts/changelog_section.py on sample changelogs the test writes (design 30 L1)."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

SCRIPT = Path(__file__).parents[3] / "scripts" / "changelog_section.py"

HEAD = """# Changelog

Some words about the format.

"""

GOOD = (
    HEAD
    + """## [Unreleased]

## [0.9.0] - 2026-12-01

### Added

- A thing.

### Fixed

- Another thing.

## [0.8.2] - 2026-11-14

### Removed
- An old thing.
"""
)


@pytest.fixture
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("changelog_section_script", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(script: ModuleType, tmp_path: Path, text: str, version: str) -> int:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(text, encoding="utf-8")
    code: int = script.main([version], changelog=changelog)
    return code


def test_a_good_heading_prints_its_section(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(script, tmp_path, GOOD, "0.9.0") == 0
    out, err = capsys.readouterr()
    assert out == "### Added\n\n- A thing.\n\n### Fixed\n\n- Another thing.\n"
    assert err == ""


def test_the_last_section_runs_to_the_end_of_the_file(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(script, tmp_path, GOOD, "0.8.2") == 0
    assert capsys.readouterr().out == "### Removed\n- An old thing.\n"


def test_the_output_has_no_heading_and_stops_before_the_next(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(script, tmp_path, GOOD, "0.9.0") == 0
    out = capsys.readouterr().out
    assert "## [" not in out
    assert "An old thing" not in out


def test_no_unreleased_heading_at_all_is_allowed(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = GOOD.replace("## [Unreleased]\n\n", "")
    assert run(script, tmp_path, text, "0.9.0") == 0
    assert capsys.readouterr().out.startswith("### Added")


@pytest.mark.parametrize(
    ("text", "version", "message"),
    [
        pytest.param(GOOD, "0.9.1", "No heading ## [0.9.1]", id="missing"),
        pytest.param(GOOD.replace("[0.9.0] - 2026-12-01", "[0.9.0]"), "0.9.0", "malformed", id="no-date"),
        pytest.param(GOOD.replace("[0.9.0] - 2026-12-01", "[0.9.0] 2026-12-01"), "0.9.0", "malformed", id="no-dash"),
        pytest.param(
            GOOD.replace("2026-12-01", "2026-13-40"), "0.9.0", "2026-13-40, which is not a valid date", id="bad-date"
        ),
        pytest.param(GOOD.replace("2026-12-01", "2026-12-1"), "0.9.0", "malformed", id="short-date"),
        pytest.param(GOOD.replace("[0.9.0]", "[0.9]"), "0.9.0", "names 0.9.0 in another form", id="short-version"),
        pytest.param(GOOD.replace("[0.9.0]", "[v0.9.0]"), "0.9.0", "names 0.9.0 in another form", id="v-prefix"),
        pytest.param(
            GOOD.replace("### Added\n\n- A thing.\n\n### Fixed\n\n- Another thing.\n", ""),
            "0.9.0",
            "is empty",
            id="empty-section",
        ),
        pytest.param(
            GOOD.replace("## [Unreleased]\n", "## [Unreleased]\n\n### Fixed\n\n- Left behind.\n"),
            "0.9.0",
            "## [Unreleased] still has entries",
            id="unreleased-entries",
        ),
        pytest.param(GOOD + "\n## [0.9.0] - 2026-12-02\n\n- Again.\n", "0.9.0", "appears 2 times", id="twice"),
        pytest.param(GOOD, "0.9", "not a version of the form X.Y.Z", id="bad-argument"),
    ],
)
def test_a_bad_changelog_exits_non_zero_with_a_message(
    script: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    text: str,
    version: str,
    message: str,
) -> None:
    assert run(script, tmp_path, text, version) == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert message in err


def test_an_empty_section_of_blank_lines_is_empty(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = HEAD + "## [0.9.0] - 2026-12-01\n\n\n   \n## [0.8.2] - 2026-11-14\n\n- Old.\n"
    assert run(script, tmp_path, text, "0.9.0") == 1
    assert "is empty" in capsys.readouterr().err


def test_a_missing_changelog_is_an_error(
    script: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert script.main(["0.9.0"], changelog=tmp_path / "CHANGELOG.md") == 1
    assert "Cannot read" in capsys.readouterr().err


def test_the_wrong_number_of_arguments_is_refused(script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    assert script.main([]) == 2
    assert "usage:" in capsys.readouterr().err


def test_as_a_child_process_it_reads_the_repository_changelog() -> None:
    """Run from its path, as the release workflow runs it. 0.0.0 has no section, so the
    script fails on the repository's own CHANGELOG.md whatever state its Unreleased section is in."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "0.0.0"], capture_output=True, text=True, check=False, encoding="utf-8"
    )
    assert result.returncode == 1
    assert result.stdout == ""
    assert result.stderr.startswith("CHANGELOG.md: ")
