"""`editor_command` and `edit_file` (design 14 F5)."""

from collections.abc import Callable

import pytest

from tests.conftest import Isolated
from tests.fakes.control import Fakes
from tlaup.config.editor import edit_file, editor_command
from tlaup.config.loader import CONFIG_HEADER
from tlaup.errors import ConfigInvalid, Failed, NotSetUp


def found(*names: str) -> Callable[[str], str | None]:
    """A `which` that knows only these programs, each at `/bin/<name>`."""
    return lambda word: f"/bin/{word}" if word in names else None


def test_visual_is_read(isolated: Isolated) -> None:
    assert editor_command({"VISUAL": "code --wait"}, which=found("code")) == ["/bin/code", "--wait"]


def test_editor_is_read(isolated: Isolated) -> None:
    assert editor_command({"EDITOR": "nano -w"}, which=found("nano")) == ["/bin/nano", "-w"]


def test_visual_wins_over_editor() -> None:
    env = {"VISUAL": "code --wait", "EDITOR": "nano"}
    assert editor_command(env, which=found("code", "nano")) == ["/bin/code", "--wait"]


def test_an_empty_visual_counts_as_unset() -> None:
    env = {"VISUAL": "", "EDITOR": "nano"}
    assert editor_command(env, which=found("nano")) == ["/bin/nano"]


def test_a_visual_of_white_space_counts_as_unset() -> None:
    env = {"VISUAL": "  ", "EDITOR": "nano"}
    assert editor_command(env, which=found("nano")) == ["/bin/nano"]


def test_a_quoted_argument_is_one_word() -> None:
    assert editor_command({"EDITOR": "'my editor' --wait"}, which=found("my editor")) == ["/bin/my editor", "--wait"]


def test_the_default_is_the_first_found_in_order() -> None:
    assert editor_command({}, which=found("sensible-editor", "nano", "vi")) == ["/bin/sensible-editor"]
    assert editor_command({}, which=found("nano", "vi")) == ["/bin/nano"]
    assert editor_command({}, which=found("vi")) == ["/bin/vi"]


def test_nothing_found_asks_for_editor() -> None:
    with pytest.raises(NotSetUp) as raised:
        editor_command({}, which=found())
    assert "EDITOR" in (raised.value.hint or "")


def test_the_default_on_windows_is_notepad() -> None:
    assert editor_command({}, os_name="nt", which=found("notepad", "vi")) == ["/bin/notepad"]
    with pytest.raises(NotSetUp):
        editor_command({}, os_name="nt", which=found("vi", "nano"))


def test_a_variable_naming_a_missing_program_is_named() -> None:
    with pytest.raises(NotSetUp) as raised:
        editor_command({"EDITOR": "nosuch --wait"}, which=found("vi"))
    assert "EDITOR" in raised.value.message
    assert "nosuch" in raised.value.message


def test_a_missing_program_in_visual_names_visual_and_does_not_fall_back() -> None:
    with pytest.raises(NotSetUp) as raised:
        editor_command({"VISUAL": "nosuch", "EDITOR": "vi"}, which=found("vi"))
    assert "VISUAL" in raised.value.message


def test_an_unbalanced_quote_is_named() -> None:
    with pytest.raises(NotSetUp) as raised:
        editor_command({"EDITOR": "'my editor"}, which=found("my editor"))
    assert "EDITOR" in raised.value.message


def editor_argv(fakes: Fakes, **script: object) -> list[str]:
    fakes.script("editor", script)
    return [str(fakes.bin / "editor")]


def test_a_file_that_was_absent_and_is_left_with_only_the_header_is_removed(isolated: Isolated, fakes: Fakes) -> None:
    argv = editor_argv(fakes)
    loaded = edit_file(isolated.paths, {}, argv)
    assert not isolated.paths.config_file.exists()
    assert loaded.settings.tlc.workers == "auto"
    assert fakes.log("editor")[0]["args"] == [str(isolated.paths.config_file)]


def test_a_file_the_editor_wrote_stays_and_is_validated(isolated: Isolated, fakes: Fakes) -> None:
    argv = editor_argv(fakes, write="tlc:\n  workers: 3\n")
    loaded = edit_file(isolated.paths, {}, argv)
    assert loaded.settings.tlc.workers == 3
    assert isolated.paths.config_file.read_text(encoding="utf-8") == "tlc:\n  workers: 3\n"


def test_an_invalid_file_stays_as_saved(isolated: Isolated, fakes: Fakes) -> None:
    argv = editor_argv(fakes, write="tlc:\n  workers: many\n")
    with pytest.raises(ConfigInvalid):
        edit_file(isolated.paths, {}, argv)
    assert isolated.paths.config_file.read_text(encoding="utf-8") == "tlc:\n  workers: many\n"


def test_an_existing_file_is_not_replaced_before_the_editor_runs(isolated: Isolated, fakes: Fakes) -> None:
    path = isolated.paths.config_file
    path.parent.mkdir(parents=True)
    path.write_text("tlc:\n  keep: true\n", encoding="utf-8")
    edit_file(isolated.paths, {}, editor_argv(fakes))
    assert path.read_text(encoding="utf-8") == "tlc:\n  keep: true\n"


def test_a_file_holding_only_the_header_is_removed(isolated: Isolated, fakes: Fakes) -> None:
    argv = editor_argv(fakes, write=CONFIG_HEADER + "\n")
    edit_file(isolated.paths, {}, argv)
    assert not isolated.paths.config_file.exists()


def test_a_non_zero_exit_is_a_failure(isolated: Isolated, fakes: Fakes) -> None:
    argv = editor_argv(fakes, exit=1)
    with pytest.raises(Failed) as raised:
        edit_file(isolated.paths, {}, argv)
    assert raised.value.exit_code == 5
    assert not isolated.paths.config_file.exists()


def test_a_program_that_cannot_start_is_a_failure(isolated: Isolated) -> None:
    with pytest.raises(Failed):
        edit_file(isolated.paths, {}, [str(isolated.work / "no-such-program")])
