"""The When steps of design 01 T5 that package 18 owns; each wraps a runner.

In-process unless one of T5's five situations applies (T12 rule 10); the in-process step refuses two
of them itself. The real-process steps are in ``_process.py``, the terminal steps in ``_terminal.py``.
Every command group is ``[^"]+``, so no form matches a longer one (each pair is tested in test_harness.py).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pytest_bdd import parsers, when

from tests.steps import _process, _terminal

if TYPE_CHECKING:
    from tests.steps._scenario import Scenario

COMMAND = r'"(?P<command>[^"]+)"'
# "to the foreground group" follows the signal it qualifies: "send SIGINT to the foreground group twice".
SEND = r"send (?P<signal>SIG[A-Z]+)(?P<group> to the foreground group)?"
TERMINAL = r"in a terminal (?P<width>\d+) by (?P<height>\d+)"
SIZE = {"width": int, "height": int}


@when(parsers.re(r'I run "(?P<command>[^"]+)"'))
def i_run(scenario: Scenario, command: str) -> None:
    scenario.run_in_process(command)


# When: a real process


@when(parsers.re(rf"I run {COMMAND} as a process"))
def i_run_as_a_process(scenario: Scenario, command: str) -> None:
    _process.run_as_process(scenario, _process.tlaup_argv(scenario, command))


@when(parsers.re(rf"I run {COMMAND} as a process with input:"))
def i_run_as_a_process_with_input(scenario: Scenario, command: str, docstring: str) -> None:
    _process.run_as_process(scenario, _process.tlaup_argv(scenario, command), "input", text=docstring)


@when(
    parsers.re(rf"I run {COMMAND} as a process whose reader closes after (?P<count>\d+) lines?"),
    converters={"count": int},
)
def i_run_as_a_process_whose_reader_closes(scenario: Scenario, command: str, count: int) -> None:
    _process.run_as_process(scenario, _process.tlaup_argv(scenario, command), "reader", lines=count)


@when(parsers.re(rf"I run {COMMAND} as a process with stdout on a closed pipe"))
def i_run_as_a_process_with_stdout_on_a_closed_pipe(scenario: Scenario, command: str) -> None:
    _process.run_as_process(scenario, _process.tlaup_argv(scenario, command), "closed-stdout")


@when(parsers.re(rf"I run {COMMAND} as a process with stdout and stderr on a closed pipe"))
def i_run_as_a_process_with_both_on_a_closed_pipe(scenario: Scenario, command: str) -> None:
    _process.run_as_process(scenario, _process.tlaup_argv(scenario, command), "closed-both")


@when(parsers.re(rf"I run {COMMAND} as a process with stdout on the null device and stderr on a closed pipe"))
def i_run_as_a_process_with_stderr_on_a_closed_pipe(scenario: Scenario, command: str) -> None:
    _process.run_as_process(scenario, _process.tlaup_argv(scenario, command), "null-and-closed")


@when(parsers.re(rf"I start {COMMAND} and {SEND} once java is running"))
def i_start_and_send_once_java_is_running(scenario: Scenario, command: str, signal: str, group: str | None) -> None:
    argv = _process.tlaup_argv(scenario, command)
    _process.start_and_signal(scenario, argv, signal, "running", group=bool(group))


@when(parsers.re(rf"I start {COMMAND} and {SEND} twice"))
def i_start_and_send_twice(scenario: Scenario, command: str, signal: str, group: str | None) -> None:
    _process.start_and_signal(scenario, _process.tlaup_argv(scenario, command), signal, "twice", group=bool(group))


@when(
    parsers.re(
        rf"I start {COMMAND} and {SEND} once java has begun its checkpoint"
        r'(?:, and again once stderr contains "(?P<text>[^"]+)")?'
    )
)
def i_start_and_send_once_java_has_begun_its_checkpoint(
    scenario: Scenario, command: str, signal: str, group: str | None, text: str | None
) -> None:
    argv = _process.tlaup_argv(scenario, command)
    again = scenario.expand(text) if text is not None else None
    _process.start_and_signal(scenario, argv, signal, "checkpoint", group=bool(group), again_once=again)


# When: a real process on a terminal


@when(parsers.re(rf"I run {COMMAND} {TERMINAL}"), converters=SIZE)
def i_run_in_a_terminal(scenario: Scenario, command: str, width: int, height: int) -> None:
    _terminal.run_in_terminal(scenario, _process.tlaup_argv(scenario, command), (width, height))


@when(
    parsers.re(rf'I run {COMMAND} {TERMINAL} with (?P<stream>stdout|stderr) redirected to "(?P<file>[^"]+)"'),
    converters=SIZE,
)
def i_run_in_a_terminal_with_a_stream_redirected(
    scenario: Scenario, command: str, width: int, height: int, stream: str, file: str
) -> None:
    argv = _process.tlaup_argv(scenario, command)
    _terminal.run_in_terminal(scenario, argv, (width, height), redirect={stream: scenario.path(file)})


@when(parsers.re(rf'I run {COMMAND} {TERMINAL} and answer "(?P<answers>[^"]*)"'), converters=SIZE)
def i_run_in_a_terminal_and_answer(scenario: Scenario, command: str, width: int, height: int, answers: str) -> None:
    argv = _process.tlaup_argv(scenario, command)
    _terminal.run_in_terminal(scenario, argv, (width, height), answers=scenario.expand(answers))


@when(
    parsers.re(
        rf"I start {COMMAND} {TERMINAL} and press Ctrl-C once the terminal has shown "
        r'"(?P<first>[^"]+)" and then "(?P<second>[^"]+)"'
    ),
    converters=SIZE,
)
def i_start_in_a_terminal_and_press_ctrl_c_once_shown(
    scenario: Scenario, command: str, width: int, height: int, first: str, second: str
) -> None:
    argv = _process.tlaup_argv(scenario, command)
    _terminal.ctrl_c_once_shown(scenario, argv, (width, height), scenario.expand(first), scenario.expand(second))


@when(parsers.re(rf"I start {COMMAND} {TERMINAL} and press Ctrl-C once java has begun its checkpoint"), converters=SIZE)
def i_start_in_a_terminal_and_press_ctrl_c_at_the_checkpoint(
    scenario: Scenario, command: str, width: int, height: int
) -> None:
    _terminal.ctrl_c_at_checkpoint(scenario, _process.tlaup_argv(scenario, command), (width, height))


@when(
    parsers.re(
        rf"I start {COMMAND} {TERMINAL} and press Ctrl-\\ once the terminal has shown "
        r'"(?P<first>[^"]+)" and then "(?P<second>[^"]+)"'
    ),
    converters=SIZE,
)
def i_start_in_a_terminal_and_press_ctrl_backslash_once_shown(
    scenario: Scenario, command: str, width: int, height: int, first: str, second: str
) -> None:
    # Package 39's form, outside T5's table: D60's Ctrl-\ reaches tlaup, which passes SIGQUIT to a parsed run's JVM.
    argv = _process.tlaup_argv(scenario, command)
    _terminal.quit_once_shown(scenario, argv, (width, height), scenario.expand(first), scenario.expand(second))
