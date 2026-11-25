"""The first run: ``ensure_tools``, ``choose_first_build`` and ``read_auto_install`` (design 12 V9).

Each test builds a ``Ui`` on in-memory streams, a real store in the test's folder with an injected clock, and
GitHub served by the ``upstream`` fixture (``responses`` over the ``releases`` recording). Assertions are on state:
the builds, the pin, the requests, and what reached stdout and stderr, never the exact wording of a message.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

from tests.unit.versioning.conftest import recorded_list
from tlaup.errors import (
    CannotAsk,
    NetworkError,
    NoPinnedBuild,
    NoToolsInstalled,
    PinnedBuildMissing,
    UsageError,
    VersionNotFound,
)
from tlaup.ui import Ui
from tlaup.versioning.first_run import choose_first_build, ensure_tools, read_auto_install
from tlaup.versioning.install import install
from tlaup.versioning.spec import VersionSpec, format_build, parse_version_spec

if TYPE_CHECKING:
    from tests.unit.versioning.conftest import Upstream
    from tlaup.versioning.remote import Release
    from tlaup.versioning.store import ToolStore

QUESTION = "Which build should tlaup install?"


class Terminal:
    """A Ui on in-memory streams with ``answers`` as stdin; ``out`` and ``err`` are what it wrote."""

    def __init__(self, answers: str = "", *, interactive: bool = True) -> None:
        self.out = io.StringIO()
        self.err = io.StringIO()
        self.ui = Ui(self.out, self.err, io.StringIO(answers), color=False, env={}, interactive=interactive)

    @property
    def questions(self) -> int:
        return self.err.getvalue().count("Choice")


def first(store: ToolStore, upstream: Upstream, text: str) -> None:
    install(store, upstream.remote, upstream.client, parse_version_spec(text))
    upstream.fake.clear()


def ensure(
    store: ToolStore,
    upstream: Upstream,
    terminal: Terminal,
    *,
    auto_install: str | None = None,
    may_install: bool = True,
) -> object:
    return ensure_tools(
        store,
        upstream.remote,
        upstream.client,
        terminal.ui,
        auto_install=auto_install,
        may_install=may_install,
    )


# ---------------------------------------------------------------------- the question


def test_answer_2_installs_and_pins_rolling_and_returns_it(store: ToolStore, upstream: Upstream) -> None:
    terminal = Terminal("2\n")
    build = ensure(store, upstream, terminal)
    assert build == store.pinned()
    assert build.name == "rolling"  # type: ignore[attr-defined]
    assert [b.name for b in store.builds()] == ["rolling"]
    assert terminal.questions == 1


def test_an_empty_line_takes_the_default_stable(store: ToolStore, upstream: Upstream) -> None:
    terminal = Terminal("\n")
    build = ensure(store, upstream, terminal)
    assert build.name == "v1.7.4"  # type: ignore[attr-defined]
    assert store.pinned() == build


def test_an_answer_outside_the_choices_asks_again(store: ToolStore, upstream: Upstream) -> None:
    terminal = Terminal("9\n1\n")
    build = ensure(store, upstream, terminal)
    assert terminal.questions == 2
    assert build.name == "v1.7.4"  # type: ignore[attr-defined]


def test_end_of_input_is_cannot_ask_and_installs_nothing(store: ToolStore, upstream: Upstream) -> None:
    with pytest.raises(CannotAsk):
        ensure(store, upstream, Terminal(""))
    assert store.builds() == []
    assert store.pinned() is None


def test_the_question_names_both_dates_on_stderr_and_writes_nothing_to_stdout(
    store: ToolStore, upstream: Upstream
) -> None:
    terminal = Terminal("1\n")
    choose_first_build(upstream.remote, terminal.ui, auto_install=None)
    stable = next(r for r in recorded_list() if r["tag_name"] == "v1.7.4")
    rolling = next(r for r in recorded_list() if r["tag_name"] == "rolling")
    jar = next(a for a in rolling["assets"] if a["name"] == "tla2tools.jar")
    text = terminal.err.getvalue()
    assert QUESTION in text
    assert "v1.7.4" in text
    assert stable["published_at"][:10] in text
    assert jar["updated_at"][:10] in text
    assert rolling["published_at"][:10] not in text or rolling["published_at"][:10] == jar["updated_at"][:10]
    assert terminal.out.getvalue() == ""
    assert upstream.list_requests == 1


def test_choose_first_build_returns_the_spec_of_the_answer(upstream: Upstream) -> None:
    assert choose_first_build(upstream.remote, Terminal("2\n").ui, auto_install=None) == VersionSpec(
        name="rolling", commit=None, calver=None, sha256=None
    )
    assert choose_first_build(upstream.remote, Terminal("1\n").ui, auto_install=None).name == "stable"


def test_the_network_failing_before_the_question_raises_its_error_and_asks_nothing(
    store: ToolStore, upstream: Upstream
) -> None:
    upstream.fake.unreachable()
    terminal = Terminal("1\n")
    with pytest.raises(NetworkError):
        ensure(store, upstream, terminal)
    assert terminal.err.getvalue() == ""
    assert store.builds() == []


def test_a_cached_list_does_not_hide_a_failing_network(store: ToolStore, upstream: Upstream) -> None:
    upstream.remote.releases()  # a fresh cache
    upstream.fake.unreachable()
    terminal = Terminal("1\n")
    with pytest.raises(NetworkError):
        choose_first_build(upstream.remote, terminal.ui, auto_install=None)
    assert terminal.err.getvalue() == ""


def test_with_no_stable_release_there_is_no_question(upstream: Upstream) -> None:
    upstream.publish_list([dict(item, prerelease=True) for item in recorded_list()])
    terminal = Terminal("1\n")
    with pytest.raises(VersionNotFound):
        choose_first_build(upstream.remote, terminal.ui, auto_install=None)
    assert terminal.err.getvalue() == ""


def test_auto_install_answers_with_no_request_and_no_question(upstream: Upstream) -> None:
    terminal = Terminal("", interactive=True)
    assert choose_first_build(upstream.remote, terminal.ui, auto_install="rolling").name == "rolling"
    assert choose_first_build(upstream.remote, terminal.ui, auto_install="stable").name == "stable"
    assert terminal.err.getvalue() == ""
    assert upstream.api_requests == 0


def test_choose_first_build_without_a_terminal_is_cannot_ask_and_makes_no_request(upstream: Upstream) -> None:
    with pytest.raises(CannotAsk):
        choose_first_build(upstream.remote, Terminal("1\n", interactive=False).ui, auto_install=None)
    assert upstream.api_requests == 0


# ---------------------------------------------------------------------- may_install false


@pytest.mark.parametrize("interactive", [True, False])
@pytest.mark.parametrize("auto_install", [None, "stable", "rolling"])
def test_may_install_false_raises_no_tools_installed_and_asks_nothing(
    store: ToolStore, upstream: Upstream, *, interactive: bool, auto_install: str | None
) -> None:
    terminal = Terminal("1\n", interactive=interactive)
    with pytest.raises(NoToolsInstalled) as error:
        ensure(store, upstream, terminal, auto_install=auto_install, may_install=False)
    assert "tlaup tool install" in (error.value.hint or "")
    assert terminal.err.getvalue() == ""
    assert upstream.api_requests == 0
    assert store.builds() == []


# ---------------------------------------------------------------------- the other rows


def test_a_pinned_build_is_returned_with_no_request(store: ToolStore, upstream: Upstream) -> None:
    first(store, upstream, "rolling")
    terminal = Terminal("", interactive=True)
    assert ensure(store, upstream, terminal) == store.pinned()
    assert upstream.api_requests == 0
    assert terminal.err.getvalue() == ""


def test_a_pinned_build_is_returned_whatever_may_install_and_auto_install_say(
    store: ToolStore, upstream: Upstream
) -> None:
    first(store, upstream, "rolling")
    pinned = store.pinned()
    assert ensure(store, upstream, Terminal(), may_install=False) == pinned
    assert ensure(store, upstream, Terminal(), auto_install="stable") == pinned
    assert upstream.api_requests == 0


def test_builds_installed_and_none_pinned_raise_no_pinned_build_naming_them(
    store: ToolStore, upstream: Upstream
) -> None:
    first(store, upstream, "rolling")
    install(store, upstream.remote, upstream.client, parse_version_spec("v1.7.4"))
    with store.locked(timeout=0):
        store.unpin()
    upstream.fake.clear()
    terminal = Terminal("1\n")
    with pytest.raises(NoPinnedBuild) as error:
        ensure(store, upstream, terminal, auto_install="stable")
    builds = store.builds()
    assert all(format_build(build, builds) in (error.value.hint or "") for build in builds)
    assert "tlaup tool pin" in (error.value.hint or "")
    assert terminal.err.getvalue() == ""
    assert upstream.api_requests == 0


def test_a_pin_naming_a_missing_build_raises_and_installs_nothing(store: ToolStore, upstream: Upstream) -> None:
    first(store, upstream, "rolling")
    (store.pinned().path / "build.json").unlink()  # type: ignore[union-attr]
    terminal = Terminal("1\n")
    with pytest.raises(PinnedBuildMissing):
        ensure(store, upstream, terminal, auto_install="rolling")
    assert upstream.api_requests == 0
    assert terminal.err.getvalue() == ""


def test_auto_install_installs_and_pins_with_one_notice_and_no_question(store: ToolStore, upstream: Upstream) -> None:
    terminal = Terminal("", interactive=False)
    build = ensure(store, upstream, terminal, auto_install="rolling")
    assert build.name == "rolling"  # type: ignore[attr-defined]
    assert store.pinned() == build
    lines = [line for line in terminal.err.getvalue().splitlines() if line.strip()]
    assert len(lines) == 1
    assert "rolling" in lines[0]
    assert upstream.client.base_url in lines[0]
    assert terminal.out.getvalue() == ""


def test_nothing_installed_and_no_terminal_and_no_answer_is_cannot_ask(store: ToolStore, upstream: Upstream) -> None:
    terminal = Terminal("1\n", interactive=False)
    with pytest.raises(CannotAsk) as error:
        ensure(store, upstream, terminal)
    assert "TLAUP_AUTO_INSTALL" in (error.value.hint or "")
    assert "tlaup tool install stable" in (error.value.hint or "")
    assert terminal.err.getvalue() == ""
    assert upstream.api_requests == 0
    assert store.builds() == []


def test_a_pin_made_by_another_tlaup_during_the_install_is_what_runs(store: ToolStore, upstream: Upstream) -> None:
    # Another tlaup installs and pins v1.7.4 after our choice and before our install adds rolling: the pin wins.
    real = upstream.remote.resolve
    done: list[bool] = []

    def resolve(spec: VersionSpec) -> Release:
        if not done:
            done.append(True)
            install(store, upstream.remote, upstream.client, parse_version_spec("v1.7.4"))
        return real(spec)

    upstream.remote.resolve = resolve  # type: ignore[method-assign]
    build = ensure(store, upstream, Terminal("2\n"))
    assert build.name == "v1.7.4"  # type: ignore[attr-defined]
    assert {b.name for b in store.builds()} == {"rolling", "v1.7.4"}


# ---------------------------------------------------------------------- read_auto_install


def test_the_option_wins_over_the_variable() -> None:
    assert read_auto_install("rolling", {"TLAUP_AUTO_INSTALL": "stable"}) == "rolling"


def test_the_variable_answers_when_there_is_no_option() -> None:
    assert read_auto_install(None, {"TLAUP_AUTO_INSTALL": "stable"}) == "stable"


@pytest.mark.parametrize("env", [{}, {"TLAUP_AUTO_INSTALL": ""}])
def test_nothing_or_an_empty_variable_is_unset(env: dict[str, str]) -> None:
    assert read_auto_install(None, env) is None


def test_an_unknown_value_from_the_option_is_a_usage_error_naming_the_option() -> None:
    with pytest.raises(UsageError) as error:
        read_auto_install("nightly", {})
    assert "--auto-install" in error.value.message
    assert "nightly" in error.value.message


def test_an_unknown_value_from_the_variable_is_a_usage_error_naming_it() -> None:
    with pytest.raises(UsageError) as error:
        read_auto_install(None, {"TLAUP_AUTO_INSTALL": "nightly"})
    assert "TLAUP_AUTO_INSTALL" in error.value.message
    assert "nightly" in error.value.message


def test_a_bad_option_is_refused_even_when_the_variable_is_good() -> None:
    with pytest.raises(UsageError):
        read_auto_install("nightly", {"TLAUP_AUTO_INSTALL": "stable"})
