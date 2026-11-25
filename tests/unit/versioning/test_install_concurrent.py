"""Two rows of 01 T6 and V11's ``.tmp/`` tests, against ``install()`` with the real client and ``fetch_build``.

``responses`` serves the ``releases`` recording (01 T4). Inventory row T9, with package 26: after a failed
download nothing of the command is left under ``.tmp/``, and a ``--force`` reinstall that fails leaves the
store as it was.
"""

from __future__ import annotations

import hashlib
import threading
from typing import TYPE_CHECKING, Any

import pytest

from tests.unit.versioning.conftest import tmp_entries
from tlaup.errors import DownloadVerificationError
from tlaup.versioning.install import InstallReport, install
from tlaup.versioning.remote import Remote
from tlaup.versioning.spec import parse_version_spec
from tlaup.versioning.store import ToolStore

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from tests.clock import FakeClock
    from tests.conftest import Isolated
    from tests.unit.versioning.conftest import Upstream
    from tlaup.paths import AppPaths
    from tlaup.versioning.github import GitHubClient


def run(store: ToolStore, upstream: Upstream, text: str, *, force: bool = False) -> InstallReport:
    return install(store, upstream.remote, upstream.client, parse_version_spec(text), force=force)


def jar_url(upstream: Upstream, tag: str) -> str:
    (asset,) = [a for a in upstream.release(tag)["assets"] if a["name"] == "tla2tools.jar"]
    url = asset["browser_download_url"]
    assert isinstance(url, str)
    return url


def cut_short(upstream: Upstream, tag: str) -> None:
    """The jar's body cut short, for the first download and the one retry."""
    body = upstream.fake.jar(tag).read_bytes()
    upstream.serve(jar_url(upstream, tag), body[: len(body) // 2], times=2)


def pin_text(isolated: Isolated) -> str | None:
    try:
        return isolated.paths.pin.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None


def test_a_failed_force_reinstall_leaves_the_store_as_it_was(
    store: ToolStore, upstream: Upstream, isolated: Isolated
) -> None:
    """T6, "``--force`` reinstall fails"."""
    installed = run(store, upstream, "v1.7.4").build
    before = store.builds()
    cut_short(upstream, "v1.7.4")
    with pytest.raises(DownloadVerificationError):
        run(store, upstream, "v1.7.4", force=True)
    assert upstream.downloads == 2  # the first download and the one retry
    assert store.builds() == before
    assert hashlib.sha256(installed.jar.read_bytes()).hexdigest() == installed.sha256
    assert pin_text(isolated) == installed.id
    assert tmp_entries(store) == []


def test_nothing_of_an_install_is_left_under_tmp(store: ToolStore, upstream: Upstream) -> None:
    """V11: neither folder nor lock file, after an install that downloaded and after one that did not."""
    run(store, upstream, "rolling")
    assert tmp_entries(store) == []
    run(store, upstream, "rolling")
    assert tmp_entries(store) == []


def test_nothing_of_a_failed_download_is_left_under_tmp(store: ToolStore, upstream: Upstream) -> None:
    """V11 and row T9: a download that fails leaves neither folder nor lock file, and adds no build."""
    cut_short(upstream, "rolling")
    with pytest.raises(DownloadVerificationError):
        run(store, upstream, "rolling")
    assert store.builds() == []
    assert tmp_entries(store) == []


class Waits(ToolStore):
    """A store that waits at a barrier before it first takes the lock: two installs both downloaded."""

    def __init__(self, paths: AppPaths, *, now: Callable[[], Any], barrier: threading.Barrier) -> None:
        super().__init__(paths, now=now)
        self._barrier: threading.Barrier | None = barrier

    def acquire(self, timeout: float = 60.0) -> None:
        if self._barrier is not None:
            barrier, self._barrier = self._barrier, None
            barrier.wait(timeout=30)
        super().acquire(timeout)


def test_two_installs_of_one_build_at_once_end_with_one_build(
    upstream: Upstream,
    isolated: Isolated,
    clock: FakeClock,
    make_client: Callable[..., GitHubClient],
    tmp_path: Path,
) -> None:
    """T6, "Two installs of one build at once": each thread its own store object, so its own lock."""
    barrier = threading.Barrier(2)
    reports: list[InstallReport] = []
    errors: list[Exception] = []

    def one() -> None:
        try:
            store = Waits(isolated.paths, now=clock.now, barrier=barrier)
            client = make_client()
            remote = Remote(client, tmp_path / "remote-cache", now=clock.now)
            reports.append(install(store, remote, client, parse_version_spec("rolling")))
        except Exception as error:  # noqa: BLE001, RUF100 - a thread's error, asserted below; RUF100 until 58
            errors.append(error)
            barrier.abort()

    threads = [threading.Thread(target=one) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
    assert errors == []
    assert len(reports) == 2
    assert all(report.downloaded for report in reports)
    assert reports[0].build.id == reports[1].build.id
    store = ToolStore(isolated.paths, now=clock.now)
    (build,) = store.builds()
    assert build.id == reports[0].build.id
    assert (build.path / "build.json").is_file()
    assert hashlib.sha256(build.jar.read_bytes()).hexdigest() == build.sha256
    assert pin_text(isolated) == build.id
    assert sorted(report.pinned for report in reports) == [False, True]
    assert tmp_entries(store) == []
    assert upstream.downloads == 2
