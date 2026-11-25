"""The expected-file helper of design 01 T8."""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tests.expected import assert_matches

REPO_ROOT = Path(__file__).parents[2]
TIMEOUT = 60


def test_a_match_passes(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    expected = tmp_path / "expected" / "out.txt"
    expected.parent.mkdir()
    expected.write_text("one\ntwo\n", encoding="utf-8")
    assert_matches("one\ntwo\n", expected, request)


def test_line_endings_are_normalised(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    expected = tmp_path / "out.txt"
    expected.write_bytes(b"one\ntwo\n")
    assert_matches("one\r\ntwo\r\n", expected, request)
    expected.write_bytes(b"one\r\ntwo\r\n")
    assert_matches("one\ntwo\n", expected, request)


def test_a_mismatch_fails_with_a_diff(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    expected = tmp_path / "out.txt"
    expected.write_text("one\ntwo\n", encoding="utf-8")
    with pytest.raises(pytest.fail.Exception) as failure:
        assert_matches("one\nthree\n", expected, request)
    message = str(failure.value)
    assert f"--- {expected}" in message
    assert "+++ actual" in message
    assert "-two\n" in message
    assert "+three\n" in message
    assert expected.read_text(encoding="utf-8") == "one\ntwo\n"


def test_a_missing_file_fails_naming_the_option(tmp_path: Path, request: pytest.FixtureRequest) -> None:
    expected = tmp_path / "expected" / "missing.txt"
    with pytest.raises(pytest.fail.Exception, match="--update-expected"):
        assert_matches("text\n", expected, request)
    assert not expected.exists()


CHILD_TESTS = """
from pathlib import Path

from tests.expected import assert_matches

HERE = Path(__file__).parent


def test_new(request):
    assert_matches("new\\n", HERE / "expected" / "deep" / "new.txt", request)


def test_changed(request):
    assert_matches("changed\\n", HERE / "expected" / "changed.txt", request)


def test_same(request):
    assert_matches("same\\n", HERE / "expected" / "same.txt", request)
"""


def run_child(folder: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-p", "no:randomly", *args, str(folder)],
        cwd=folder,
        capture_output=True,
        text=True,
        timeout=TIMEOUT,
        check=False,
    )


@pytest.fixture
def child_suite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A pytest suite in tmp_path that uses the helper through the real conftest hooks."""
    folder = tmp_path / "suite"
    (folder / "expected").mkdir(parents=True)
    (folder / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (folder / "conftest.py").write_text(
        "from tests.conftest import pytest_addoption, pytest_terminal_summary  # noqa: F401\n", encoding="utf-8"
    )
    (folder / "test_child.py").write_text(textwrap.dedent(CHILD_TESTS), encoding="utf-8")
    (folder / "expected" / "changed.txt").write_text("before\n", encoding="utf-8")
    (folder / "expected" / "same.txt").write_text("same\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(REPO_ROOT))
    return folder


def test_without_the_option_the_child_fails(child_suite: Path) -> None:
    result = run_child(child_suite)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "2 failed, 1 passed" in result.stdout
    assert "--update-expected" in result.stdout
    assert (child_suite / "expected" / "changed.txt").read_text(encoding="utf-8") == "before\n"
    assert "expected files written" not in result.stdout


def test_with_the_option_files_are_written_and_listed(child_suite: Path) -> None:
    result = run_child(child_suite, "--update-expected")
    assert result.returncode == 0, result.stdout + result.stderr
    new = child_suite / "expected" / "deep" / "new.txt"
    changed = child_suite / "expected" / "changed.txt"
    assert new.read_text(encoding="utf-8") == "new\n"
    assert changed.read_text(encoding="utf-8") == "changed\n"
    summary = result.stdout.split("expected files written by --update-expected", 1)[1]
    listed = [line for line in summary.splitlines() if line.endswith(".txt")]
    assert sorted(listed) == sorted([str(new), str(changed)])
    again = run_child(child_suite)
    assert again.returncode == 0, again.stdout + again.stderr
