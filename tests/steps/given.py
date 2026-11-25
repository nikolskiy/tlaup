"""The Given steps of design 01 T5 that package 18 owns; each wraps a method of ``Scenario``.

The vocabulary is closed: a new step needs a reason in its pull request. Later packages add their own
functions here (29, 31) and edit none of these.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import given, parsers

from tests.steps import _store

if TYPE_CHECKING:
    import pytest

    from tests.steps._scenario import Scenario

# Given: files


@given(parsers.re(r'a spec "(?P<name>[^"]+)" from the golden specs'))
def a_spec_from_the_golden_specs(scenario: Scenario, name: str) -> None:
    scenario.spec_from_golden(name)


@given(parsers.re(r'a file "(?P<path>[^"]+)" containing:'))
def a_file_containing(scenario: Scenario, path: str, docstring: str) -> None:
    scenario.write_file(path, docstring)


@given(parsers.re(r"the config file contains:"))
def the_config_file_contains(scenario: Scenario, docstring: str) -> None:
    scenario.write_config(docstring)


@given(parsers.re(r'the folder "(?P<path>[^"]+)" is read-only'))
def the_folder_is_read_only(scenario: Scenario, path: str) -> None:
    scenario.read_only(path)


@given(parsers.re(r'I am in the folder "(?P<path>[^"]+)"'))
def i_am_in_the_folder(scenario: Scenario, path: str) -> None:
    scenario.enter_folder(path)


# Given: what Java does; each declares one run of the fake


@given(parsers.re(r'java replays "(?P<case>[^"]+)" with exit code (?P<code>\d+)'), converters={"code": int})
def java_replays(scenario: Scenario, case: str, code: int) -> None:
    scenario.java_replays(case, code)


@given(parsers.re(r"java prints (?P<count>\d+) lines"), converters={"count": int})
def java_prints_lines(scenario: Scenario, count: int) -> None:
    scenario.java_prints(count)


@given(parsers.re(r'java writes "(?P<out>.*)" to stdout and "(?P<err>.*)" to stderr'))
def java_writes_to_stdout_and_stderr(scenario: Scenario, out: str, err: str) -> None:
    scenario.java_writes(out, err)


@given(parsers.re(r"java echoes its input"))
def java_echoes_its_input(scenario: Scenario) -> None:
    scenario.java_echoes()


# Given: changes to the run declared last


@given(parsers.re(r"java hangs after line (?P<line>\d+)"), converters={"line": int})
def java_hangs_after_line(scenario: Scenario, line: int) -> None:
    scenario.change_run(hang_after_line=line)


@given(parsers.re(r"java pauses (?P<ms>\d+) ms between lines"), converters={"ms": int})
def java_pauses_between_lines(scenario: Scenario, ms: int) -> None:
    scenario.change_run(line_delay_ms=ms)


@given(parsers.re(r'java writes "(?P<names>[^"]+)" into its metadir'))
def java_writes_into_its_metadir(scenario: Scenario, names: str) -> None:
    scenario.metadir_files(names)


@given(
    parsers.re(r"java begins a checkpoint after line (?P<begin>\d+) and commits it before line (?P<commit>\d+)"),
    converters={"begin": int, "commit": int},
)
def java_begins_a_checkpoint(scenario: Scenario, begin: int, commit: int) -> None:
    scenario.checkpoint(begin, commit)


@given(parsers.re(r"""java's output has "(?P<old>.*)" replaced by "(?P<new>.*)\""""))
def javas_output_has_text_replaced(scenario: Scenario, old: str, new: str) -> None:
    scenario.replace_output(old, new)


@given(parsers.re(r"java ignores (?P<signal>SIG[A-Z]+)"))
def java_ignores_signal(scenario: Scenario, signal: str) -> None:
    scenario.on_signal(signal, "ignore")


@given(parsers.re(r"java exits with (?P<code>\d+) on (?P<signal>SIG[A-Z]+)"), converters={"code": int})
def java_exits_with_code_on_signal(scenario: Scenario, code: int, signal: str) -> None:
    scenario.on_signal(signal, code)


# Given: which Java there is


@given(parsers.re(r"java is not installed"))
def java_is_not_installed(scenario: Scenario) -> None:
    scenario.not_installed("java")


@given(parsers.re(r"java is not executable"))
def java_is_not_executable(scenario: Scenario) -> None:
    scenario.not_executable("java")


@given(parsers.re(r'java is version "(?P<version>[^"]+)"'))
def java_is_version(scenario: Scenario, version: str) -> None:
    scenario.java_version(version)


@given(parsers.re(r'java is replaced by version "(?P<version>[^"]+)"'))
def java_is_replaced_by_version(scenario: Scenario, version: str) -> None:
    scenario.java_replaced_by(version)


@given(parsers.re(r"java takes (?P<seconds>\d+) seconds to report its version"), converters={"seconds": int})
def java_takes_seconds_to_report_its_version(scenario: Scenario, seconds: int) -> None:
    scenario.java_version_delay(seconds)


@given(
    parsers.re(
        r'java answers its version check with "(?P<text>.*)" on (?P<stream>stdout|stderr) and exit code (?P<code>\d+)'
    ),
    converters={"code": int},
)
def java_answers_its_version_check(scenario: Scenario, text: str, stream: str, code: int) -> None:
    scenario.java_version_answer(text, stream, code)


@given(parsers.re(r'JAVA_HOME is a JDK of version "(?P<version>[^"]+)"'))
def java_home_is_a_jdk(scenario: Scenario, version: str) -> None:
    scenario.java_home_jdk(version)


@given(parsers.re(r"JAVA_HOME is an empty folder"))
def java_home_is_an_empty_folder(scenario: Scenario) -> None:
    scenario.java_home_empty()


@given(parsers.re(r"javac is not installed"))
def javac_is_not_installed(scenario: Scenario) -> None:
    scenario.not_installed("javac")


@given(parsers.re(r'javac is version "(?P<version>[^"]+)"'))
def javac_is_version(scenario: Scenario, version: str) -> None:
    scenario.javac_version(version)


# Given: the editor


@given(parsers.re(r"the editor writes:"))
def the_editor_writes(scenario: Scenario, docstring: str) -> None:
    scenario.editor(write=scenario.expand(docstring))


@given(parsers.re(r"the editor exits with code (?P<code>\d+)"), converters={"code": int})
def the_editor_exits_with_code(scenario: Scenario, code: int) -> None:
    scenario.editor(exit=code)


# Given: the rest


@given(parsers.re(r'the environment variable "(?P<name>[^"]+)" is "(?P<value>.*)"'))
def the_environment_variable_is(scenario: Scenario, name: str, value: str) -> None:
    scenario.set_env(name, value)


# Given: the store (package 29)


@given(parsers.re(r'the build "(?P<spec>[^"]+)" is installed(?P<pinned> and pinned)?'))
def the_build_is_installed(scenario: Scenario, spec: str, pinned: str | None) -> None:
    _store.install(scenario, spec, pinned=bool(pinned))


@given(parsers.re(r"no build is installed"))
def no_build_is_installed(scenario: Scenario) -> None:
    _store.no_build(scenario)


@given(
    parsers.re(r'the release list is cached from "(?P<recording>[^"]+)", (?P<minutes>\d+) minutes? old'),
    converters={"minutes": int},
)
def the_release_list_is_cached(
    scenario: Scenario, request: pytest.FixtureRequest, recording: str, minutes: int
) -> None:
    _store.cache_releases(scenario, request, recording, minutes)


@given(parsers.re(r'the jar of the build "(?P<spec>[^"]+)" is truncated'))
def the_jar_of_the_build_is_truncated(scenario: Scenario, spec: str) -> None:
    _store.truncate(scenario, spec)


# Given: GitHub (package 29; in-process only)


@given(parsers.re(r'GitHub answers from "(?P<recording>[^"]+)"'))
def github_answers_from(scenario: Scenario, request: pytest.FixtureRequest, recording: str) -> None:
    _store.github(scenario, request, recording)


@given(parsers.re(r'GitHub answers (?P<status>\d+) to "(?P<path>[^"]+)"'), converters={"status": int})
def github_answers_status_to(scenario: Scenario, request: pytest.FixtureRequest, status: int, path: str) -> None:
    _store.github(scenario, request).answer(status, scenario.expand(path))


@given(parsers.re(r"GitHub is unreachable"))
def github_is_unreachable(scenario: Scenario, request: pytest.FixtureRequest) -> None:
    _store.github(scenario, request).unreachable()
