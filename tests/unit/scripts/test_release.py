"""The questions and texts of scripts/release.py (design 30 L8). Its git, gh and uv steps are
proven by the first release; nothing here runs them."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from types import ModuleType

SCRIPT = Path(__file__).parents[3] / "scripts" / "release.py"


@pytest.fixture
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("release_script", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def answers(*given: str) -> tuple[Callable[[str], str], list[str]]:
    """An ``input`` that gives these answers in turn, and the prompts it was shown."""
    queue = list(given)
    prompts: list[str] = []

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return queue.pop(0)

    return ask, prompts


def test_each_part_bumps_as_uv_does(script: ModuleType) -> None:
    assert script.next_versions("0.8.2") == {"patch": "0.8.3", "minor": "0.9.0", "major": "1.0.0"}
    assert script.next_versions("1.9.9") == {"patch": "1.9.10", "minor": "1.10.0", "major": "2.0.0"}


@pytest.mark.parametrize("version", ["0.9", "0.9.0rc1", "v0.9.0", ""])
def test_a_version_not_of_the_form_x_y_z_is_refused(script: ModuleType, version: str) -> None:
    with pytest.raises(script.ReleaseError, match=r"not of the form X\.Y\.Z"):
        script.next_versions(version)


def test_the_part_question_shows_what_each_part_gives_and_asks_again_until_answered(
    script: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    ask, prompts = answers("medium", " Minor ")
    assert script.ask_part("0.8.2", ask) == "minor"
    assert prompts[0] == "Version 0.8.2. Bump which part? (patch 0.8.3, minor 0.9.0, major 1.0.0; empty to stop): "
    assert len(prompts) == 2
    assert "Answer patch, minor or major." in capsys.readouterr().out


def test_an_empty_part_answer_stops(script: ModuleType) -> None:
    ask, _ = answers("  ")
    assert script.ask_part("0.8.2", ask) is None


@pytest.mark.parametrize(
    ("given", "default", "expected"),
    [
        (("",), True, True),
        (("",), False, False),
        (("y",), False, True),
        (("YES",), False, True),
        (("n",), True, False),
        (("maybe", "no"), True, False),
    ],
)
def test_a_yes_or_no_question(script: ModuleType, given: tuple[str, ...], *, default: bool, expected: bool) -> None:
    ask, prompts = answers(*given)
    assert script.ask_yes("Go?", default=default, ask=ask) is expected
    assert prompts[0] == ("Go? [Y/n] " if default else "Go? [y/N] ")
    assert len(prompts) == len(given)


def test_the_pull_request_text_says_what_merging_does_then_gives_the_section(script: ModuleType) -> None:
    body = script.pr_body("0.9.0", "### Added\n\n- A thing.\n")
    first, rest = body.split("\n\n", 1)
    assert first.startswith("Release tlaup 0.9.0. Once Test is green, auto-merge squash-merges this into main")
    assert "tags the commit v0.9.0" in first
    assert "\n" not in first  # one line, so GitHub's wrapping of the squash message stays clean
    assert rest == "### Added\n\n- A thing.\n"


def test_it_takes_no_arguments(script: ModuleType, capsys: pytest.CaptureFixture[str]) -> None:
    assert script.main(["minor"]) == 2
    assert "it asks for everything it needs" in capsys.readouterr().err


def _eof(prompt: str) -> str:
    raise EOFError


def test_ctrl_d_at_the_part_question_stops_like_ctrl_c(script: ModuleType) -> None:
    with pytest.raises(KeyboardInterrupt):
        script.ask_part("0.8.2", _eof)


@pytest.mark.parametrize("default", [True, False])
def test_ctrl_d_at_a_yes_or_no_question_stops_like_ctrl_c(script: ModuleType, *, default: bool) -> None:
    with pytest.raises(KeyboardInterrupt):
        script.ask_yes("Go?", default=default, ask=_eof)


def test_undo_does_nothing_for_a_branch_this_run_did_not_make(script: ModuleType) -> None:
    assert script.Local("release/v0.9.0").undo() == "nothing was changed."


def test_undo_of_a_pushed_branch_says_what_is_left_and_runs_nothing(script: ModuleType) -> None:
    local = script.Local("release/v0.9.0")
    local.created = True
    local.pushed = True
    said = local.undo()
    assert "release/v0.9.0 is pushed already" in said
    assert "git push origin --delete release/v0.9.0" in said


def test_the_changed_files_are_the_tracked_changes_and_the_untracked_files(script: ModuleType) -> None:
    said = {
        ("git", "diff", "--name-only", "HEAD"): "CHANGELOG.md\npyproject.toml\nuv.lock",
        ("git", "ls-files", "--others", "--exclude-standard"): "notes.txt",
    }
    assert script.changed_paths(lambda *args: said[args]) == {*script.FILES, "notes.txt"}


def test_a_tree_with_only_the_release_files_changed_names_each_one_whole(script: ModuleType) -> None:
    said = {
        ("git", "diff", "--name-only", "HEAD"): "CHANGELOG.md\npyproject.toml\nuv.lock",
        ("git", "ls-files", "--others", "--exclude-standard"): "",
    }
    assert script.changed_paths(lambda *args: said[args]) == set(script.FILES)
