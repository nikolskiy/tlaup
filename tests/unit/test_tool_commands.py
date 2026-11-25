"""The `tool` commands' plain functions, where a feature scenario cannot reach (design 12 V12, V7; inventory T11).

Each test calls the command's function with a `Ui` on in-memory streams, the store and the client built with
the injected clock, and GitHub served by package 05's recordings.
"""

from __future__ import annotations

import io
import json
import os
import stat
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
import responses

import tlaup.cli
from tests.clock import FakeClock
from tests.github import BASE
from tests.steps._store import add_build, published_jars, recorded_releases
from tlaup.cmd.tool._shared import download_progress
from tlaup.cmd.tool.install import install_tools
from tlaup.cmd.tool.upgrade import upgrade_tools
from tlaup.errors import TlaupError
from tlaup.ui import Ui
from tlaup.versioning.github import GitHubClient
from tlaup.versioning.remote import Remote, write_cache
from tlaup.versioning.spec import parse_version_spec
from tlaup.versioning.store import ToolStore

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.conftest import Isolated
    from tests.github import GitHubFake

V174_JAR = "https://github.com/tlaplus/tlaplus/releases/download/v1.7.4/tla2tools.jar"
SIGNED = "https://objects.example.org/tla2tools.jar"
SIGNATURE = "secret-value"
READ_ONLY_REASON = "folder permissions bind neither on Windows nor for root (D15)"


def make_ui(stdin: str = "", **kwargs: Any) -> tuple[Ui, io.StringIO, io.StringIO]:
    out, err = io.StringIO(), io.StringIO()
    return Ui(out, err, io.StringIO(stdin), color=False, env={}, **kwargs), out, err


def parts(isolated: Isolated, clock: FakeClock) -> tuple[ToolStore, Remote, GitHubClient]:
    store = ToolStore(isolated.paths, now=clock.now)
    client = GitHubClient(BASE, token=None, token_hosts=[], user_agent="tlaup-test", sleep=clock.sleep)
    return store, Remote(client, isolated.paths.remote, now=clock.now), client


def test_install_with_no_version_asks_and_installs_the_build_chosen(
    isolated: Isolated, github: Callable[..., GitHubFake], tmp_path: Path
) -> None:
    clock = FakeClock()
    store, remote, client = parts(isolated, clock)
    add_build(store, tmp_path, "v1.7.4", pinned=True)
    github("releases")
    ui, out, err = make_ui("2\n", interactive=True)

    code = install_tools(store, remote, client, ui, None, force=False, env={}, progress=None)

    assert code == 0
    assert [build.name for build in store.builds()] == ["rolling", "v1.7.4"]
    assert store.pinned() is not None
    assert store.pinned().name == "v1.7.4"  # type: ignore[union-attr]
    text = err.getvalue()
    assert text.startswith("Which build should tlaup install?\n  1) stable   v1.7.4, released 2024-08-05\n")
    assert "Choice [1]: " in text
    assert "rolling@bc1b506 installed beside" not in text  # another name: no build of rolling was there
    assert "Installed rolling@bc1b506" in text
    assert out.getvalue() == ""


def test_the_download_shows_a_bar_with_the_size_and_a_speed_on_a_terminal_row_t11(
    isolated: Isolated, github: Callable[..., GitHubFake], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TERM", "xterm-256color")  # under TERM=dumb Rich's live display writes nothing (T2)
    clock = FakeClock()
    store, remote, client = parts(isolated, clock)
    fake = github("releases")
    body = fake.jar("v1.7.4").read_bytes()
    size = len(body)
    # GitHub's object store sends a Content-Length, which the recordings leave out; the bar's total comes from it.
    sized = responses.Response("GET", V174_JAR, body=body, status=200, headers={"Content-Length": str(size)})
    fake.mock.registered().insert(0, sized)
    ui, out, err = make_ui(terminal=True, size=(100, 30))

    with download_progress(ui) as progress:
        install_tools(store, remote, client, ui, parse_version_spec("v1.7.4"), force=False, env={}, progress=progress)

    text = err.getvalue()
    bar, _, notes = text.rpartition("\n\x1b[?25h")  # the bar's last frame, then the cursor shown again
    assert f"{size}/{size} bytes" in bar.rsplit("\r", 1)[-1]
    assert "B/s" in bar.rsplit("\r", 1)[-1]
    assert "tla2tools.jar" in bar
    assert notes == "Installed v1.7.4@5a47802\nPinned v1.7.4@5a47802\n"
    assert out.getvalue() == ""


def test_no_bar_when_stderr_is_not_a_terminal(isolated: Isolated, github: Callable[..., GitHubFake]) -> None:
    clock = FakeClock()
    store, remote, client = parts(isolated, clock)
    github("releases")
    ui, _, err = make_ui()

    with download_progress(ui) as progress:
        install_tools(store, remote, client, ui, parse_version_spec("v1.7.4"), force=False, env={}, progress=progress)

    assert err.getvalue() == "Installed v1.7.4@5a47802\nPinned v1.7.4@5a47802\n"


def _redirect_to_signed(fake: GitHubFake, *, times: int) -> None:
    for _ in range(times):
        redirect = responses.Response("GET", V174_JAR, status=302, headers={"Location": f"{SIGNED}?sig={SIGNATURE}"})
        fake.mock.registered().insert(0, redirect)


def test_a_signed_download_address_is_not_recorded_in_build_json(
    isolated: Isolated, github: Callable[..., GitHubFake]
) -> None:
    clock = FakeClock()
    store, remote, client = parts(isolated, clock)
    fake = github("releases")
    _redirect_to_signed(fake, times=1)
    fake.mock.add("GET", SIGNED, body=fake.jar("v1.7.4").read_bytes(), status=200, content_type="application/zip")
    ui, _, _ = make_ui()

    install_tools(store, remote, client, ui, parse_version_spec("v1.7.4"), force=False, env={}, progress=None)

    assert any(SIGNED in (request.url or "") for request in fake.requests)  # the redirect was followed
    records = list(isolated.paths.tools.glob("*/build.json"))
    assert len(records) == 1
    for record in records:
        text = record.read_text(encoding="utf-8")
        assert SIGNATURE not in text
        assert json.loads(text)["source"]["url"] == V174_JAR


def test_a_signed_download_address_is_not_printed_when_the_body_fails_under_debug(
    isolated: Isolated, github: Callable[..., GitHubFake], capsys: pytest.CaptureFixture[str]
) -> None:
    clock = FakeClock()
    store, remote, client = parts(isolated, clock)
    fake = github("releases")
    _redirect_to_signed(fake, times=2)  # the first download and its one retry (V5)
    short = responses.Response(
        "GET", SIGNED, body=b"PK", status=200, headers={"Content-Length": "838"}, auto_calculate_content_length=False
    )
    fake.mock.add(short)
    ui, out, err = make_ui()

    with pytest.raises(TlaupError) as caught:
        install_tools(store, remote, client, ui, parse_version_spec("v1.7.4"), force=False, env={}, progress=None)
    tlaup.cli.report(caught.value, None, ["--debug"])  # what the root group prints for it under --debug

    printed = capsys.readouterr()
    assert sum(SIGNED in (request.url or "") for request in fake.requests) == 2  # both bodies failed
    assert "Traceback" in printed.err
    for text in (printed.out, printed.err, out.getvalue(), err.getvalue()):
        assert SIGNATURE not in text
    assert store.builds() == []


# What upgrade prints for a case no scenario can set up: the old build cannot be removed after the upgrade.


@pytest.mark.skipif(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0), reason=READ_ONLY_REASON)
def test_an_upgrade_whose_old_build_cannot_be_removed_says_what_was_done_and_exits_5(
    isolated: Isolated, github: Callable[..., GitHubFake], tmp_path: Path
) -> None:
    clock = FakeClock()
    store, remote, client = parts(isolated, clock)
    old = add_build(store, tmp_path, "rolling@1a2b3c4", pinned=True)
    github("releases")
    mode = stat.S_IMODE(old.path.stat().st_mode)
    old.path.chmod(mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))  # a folder that cannot be moved out
    ui, out, err = make_ui()
    try:
        code = upgrade_tools(store, remote, client, ui, parse_version_spec("rolling"), progress=None)
    finally:
        old.path.chmod(mode)

    assert code == 5
    lines = err.getvalue().splitlines()
    assert lines[:2] == ["Upgraded rolling@1a2b3c4 to rolling@bc1b506", "Pinned rolling@bc1b506"]
    assert lines[2].startswith("error: rolling@1a2b3c4 was not removed: cannot remove ")
    assert len(lines) == 3
    assert out.getvalue() == ""
    assert old.id in [build.id for build in store.builds()]  # the old build is intact


@pytest.mark.skipif(not Path("/dev/full").exists(), reason="/dev/full exists on Linux only")
def test_tool_list_with_stdout_on_dev_full_exits_5(isolated: Isolated, tmp_path: Path) -> None:
    # 02 X1: a full disk under the table is "cannot write output" and 5. A real process, from a store that already
    # holds two builds and a fresh cache, so that it asks no one.
    store = ToolStore(isolated.paths, now=FakeClock().now)
    add_build(store, tmp_path, "v1.7.4", pinned=True)
    add_build(store, tmp_path, "rolling")
    url = f"{os.environ['TLAUP_TOOL_REPOSITORY']}/releases"
    write_cache(isolated.paths.remote, url, recorded_releases("releases", published_jars(tmp_path)), datetime.now(UTC))
    with Path("/dev/full").open("wb") as full:
        done = subprocess.run(
            [sys.executable, "-m", "tlaup", "tool", "list"],
            stdin=subprocess.DEVNULL,
            stdout=full,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
            check=False,
        )
    assert done.returncode == 5
    assert "cannot write output" in done.stderr
    assert "Traceback" not in done.stderr
