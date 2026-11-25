"""The Then steps of design 01 T5 that package 18 owns; each wraps a method of ``Scenario``.

The result steps speak about the last run; the fakes' steps read the whole log of the scenario (T5).
Later packages add their own functions here (29, 31, 39, 40) and edit none of these.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from pytest_bdd import parsers, then

if TYPE_CHECKING:
    from tests.fakes.control import Tool
    from tests.steps._scenario import Scenario

STREAM = r"(?P<stream>stdout|stderr)"
TOOL = r"(?P<tool>java|javac|git|the editor)"


def _tool(name: str) -> Tool:
    return cast("Tool", "editor" if name == "the editor" else name)


# Then: the result


@then(parsers.re(r"the exit code is (?P<code>\d+)"), converters={"code": int})
def the_exit_code_is(scenario: Scenario, code: int) -> None:
    scenario.check_exit_code(code)


@then(parsers.re(rf'{STREAM} contains "(?P<text>.*)"'))
def stream_contains(scenario: Scenario, stream: str, text: str) -> None:
    scenario.check_contains(stream, text)


@then(parsers.re(rf'{STREAM} contains "(?P<text>.*)" (?P<times>\d+) times'), converters={"times": int})
def stream_contains_times(scenario: Scenario, stream: str, text: str, times: int) -> None:
    scenario.check_contains(stream, text, times)


@then(parsers.re(rf'{STREAM} does not contain "(?P<text>.*)"'))
def stream_does_not_contain(scenario: Scenario, stream: str, text: str) -> None:
    scenario.check_not_contains(stream, text)


@then(parsers.re(rf'{STREAM} is exactly "(?P<text>.*)"'))
def stream_is_exactly(scenario: Scenario, stream: str, text: str) -> None:
    scenario.check_exactly(stream, text)


@then(parsers.re(rf"{STREAM} is empty"))
def stream_is_empty(scenario: Scenario, stream: str) -> None:
    scenario.check_empty(stream)


@then(parsers.re(rf'{STREAM} matches the expected file "(?P<name>[^"]+)"'))
def stream_matches_the_expected_file(scenario: Scenario, stream: str, name: str) -> None:
    scenario.check_matches(scenario.stream(stream), name)


# Then: files and the cache


@then(parsers.re(r'the file "(?P<path>[^"]+)" exists'))
def the_file_exists(scenario: Scenario, path: str) -> None:
    scenario.check_file(path, exists=True)


@then(parsers.re(r'the file "(?P<path>[^"]+)" does not exist'))
def the_file_does_not_exist(scenario: Scenario, path: str) -> None:
    scenario.check_file(path, exists=False)


@then(parsers.re(r'the file "(?P<path>[^"]+)" contains "(?P<text>.*)"'))
def the_file_contains(scenario: Scenario, path: str, text: str) -> None:
    scenario.check_file_contains(path, text)


@then(parsers.re(r'the file "(?P<path>[^"]+)" matches the expected file "(?P<name>[^"]+)"'))
def the_file_matches_the_expected_file(scenario: Scenario, path: str, name: str) -> None:
    scenario.check_matches(scenario.file_text(path), name)


@then(parsers.re(r"the config file is unchanged"))
def the_config_file_is_unchanged(scenario: Scenario) -> None:
    scenario.check_config_unchanged()


@then(parsers.re(r"the cache holds no run folders"))
def the_cache_holds_no_run_folders(scenario: Scenario) -> None:
    scenario.check_run_folders(0)


@then(parsers.re(r"the cache holds (?P<count>\d+) run folders?"), converters={"count": int})
def the_cache_holds_run_folders(scenario: Scenario, count: int) -> None:
    scenario.check_run_folders(count)


@then(parsers.re(r"the cache holds no lock files"))
def the_cache_holds_no_lock_files(scenario: Scenario) -> None:
    scenario.check_no_lock_files()


# Then: the fakes


@then(parsers.re(rf"{TOOL} was started (?P<times>\d+) times?"), converters={"times": int})
def tool_was_started_times(scenario: Scenario, tool: str, times: int) -> None:
    scenario.check_started(_tool(tool), times)


@then(parsers.re(rf"{TOOL} was not started"))
def tool_was_not_started(scenario: Scenario, tool: str) -> None:
    scenario.check_started(_tool(tool), 0)


@then(parsers.re(rf'{TOOL} was started with "(?P<argument>.*)"'))
def tool_was_started_with(scenario: Scenario, tool: str, argument: str) -> None:
    scenario.check_started_with(_tool(tool), argument, present=True)


@then(parsers.re(rf'{TOOL} was started without "(?P<argument>.*)"'))
def tool_was_started_without(scenario: Scenario, tool: str, argument: str) -> None:
    scenario.check_started_with(_tool(tool), argument, present=False)


@then(parsers.re(r'java ran "(?P<main>[^"]+)" (?P<times>\d+) times?'), converters={"times": int})
def java_ran_times(scenario: Scenario, main: str, times: int) -> None:
    scenario.check_ran(main, times)


@then(parsers.re(r'java did not run "(?P<main>[^"]+)"'))
def java_did_not_run(scenario: Scenario, main: str) -> None:
    scenario.check_ran(main, 0)


@then(parsers.re(r'java was started in the folder "(?P<path>[^"]+)"'))
def java_was_started_in_the_folder(scenario: Scenario, path: str) -> None:
    scenario.check_started_in(path)


@then(parsers.re(r"java ran from JAVA_HOME"))
def java_ran_from_java_home(scenario: Scenario) -> None:
    scenario.check_ran_from_java_home()


@then(parsers.re(r"java ran from PATH"))
def java_ran_from_path(scenario: Scenario) -> None:
    scenario.check_ran_from_path()


@then(parsers.re(r'the java command matches the expected file "(?P<name>[^"]+)"'))
def the_java_command_matches_the_expected_file(scenario: Scenario, name: str) -> None:
    scenario.check_matches(scenario.java_command(), name)


@then(parsers.re(r"the java process has exited"))
def the_java_process_has_exited(scenario: Scenario) -> None:
    scenario.check_java_exited()
