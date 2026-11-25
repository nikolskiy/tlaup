"""A store in the test's folder and small real jars put into it the way a download does (design 12 V1)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.clock import FakeClock
from tests.github import BASE, RECORDINGS
from tests.jars import make_tools_jar
from tlaup.versioning.github import GitHubClient
from tlaup.versioning.jarinfo import read_jar
from tlaup.versioning.store import Build, Source, TmpFolder, ToolStore

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Iterator

    import requests

    from tests.conftest import Isolated
    from tlaup.errors import TlaupError
    from tlaup.versioning.jarinfo import JarInfo

SOURCE = Source(
    kind="github-release",
    url="https://example.invalid/rolling/tla2tools.jar",
    asset_id=1,
    asset_updated_at="2026-11-15T00:30:00Z",
    digest_checked=True,
)


def commit(prefix: str) -> str:
    """A 40-digit commit that starts with ``prefix``."""
    return prefix.ljust(40, "0")


def manifest(commit: str | None = None, built_at: str | None = None, extra: str = "") -> bytes:
    """A manifest with the entries ``read_jar`` reads; ``extra`` makes otherwise equal jars differ."""
    lines = ["Manifest-Version: 1.0"]
    if commit is not None:
        lines.append(f"X-Git-Revision: {commit}")
    if built_at is not None:
        lines.append(f"Build-TimeStamp: {built_at}")
    if extra:
        lines.append(f"X-Test: {extra}")
    return ("\n".join(lines) + "\n").encode()


class Downloads:
    """Jars in temporary folders of the store, as a download leaves them; each folder released at the end."""

    def __init__(self, store: ToolStore) -> None:
        self.store = store
        self.held: list[TmpFolder] = []

    def jar(self, data: bytes) -> tuple[Path, JarInfo]:
        tmp = self.store.new_tmp()
        tmp.lock()
        tmp.make()
        self.held.append(tmp)
        jar = make_tools_jar(tmp.path / "tla2tools.jar", data)
        return jar, read_jar(jar)

    def add(self, data: bytes, name: str = "rolling", *, prerelease: bool = True, repair: bool = False) -> Build:
        """Download ``data`` and add it under the store lock."""
        jar, info = self.jar(data)
        with self.store.locked(timeout=0):
            return self.store.add(jar, info, name=name, prerelease=prerelease, source=SOURCE, repair=repair)

    def release(self) -> None:
        for tmp in self.held:
            tmp.release()
        self.held = []


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store(isolated: Isolated, clock: FakeClock) -> ToolStore:
    return ToolStore(isolated.paths, now=clock.now)


@pytest.fixture
def downloads(store: ToolStore) -> Iterator[Downloads]:
    made = Downloads(store)
    yield made
    made.release()


def make_build(name: str, build_id: str | None = None, **fields: object) -> Build:
    """A ``Build`` value with no folder behind it, for the order and the printed form."""
    values: dict[str, object] = {
        "commit": None,
        "calver": None,
        "built_at": None,
        "sha256": "0" * 64,
        "size": 1,
        "prerelease": False,
        "source": SOURCE,
        "installed_at": "2026-11-15T00:00:00Z",
        "capabilities": frozenset(),
    }
    values.update(fields)
    build_id = build_id or f"{name}-{str(values['sha256'])[:12]}"
    return Build(id=build_id, name=name, path=Path("/nowhere") / build_id, **values)


# --- the GitHub client (design 12 V7) ---

TOKEN = "test-token-not-a-secret-0123"  # a made-up value; tests assert on it through the helpers below
USER_AGENT = "tlaup/0.0.0-test"


def has_authorization(request: requests.PreparedRequest) -> bool:
    """Whether the request carried any Authorization header (a bool, so no failing assert prints a value)."""
    return "Authorization" in request.headers


def has_token(request: requests.PreparedRequest) -> bool:
    """Whether the request carried the test token as a bearer header."""
    return request.headers.get("Authorization") == f"Bearer {TOKEN}"


def secret_free(error: TlaupError, *secrets: str) -> bool:
    """Whether none of ``secrets`` is in the error's text, message, hint, details or repr."""
    text = " ".join(str(part) for part in (error, error.message, error.hint, error.details, repr(error)))
    return not any(secret in text for secret in secrets)


def printable_only(error: TlaupError) -> bool:
    """Whether every character of the error's message, hint and details is printable."""
    return all(part is None or part.isprintable() for part in (error.message, error.hint, error.details))


@pytest.fixture
def make_client(clock: FakeClock) -> Callable[..., GitHubClient]:
    """``make_client(base_url=BASE, token=None, token_hosts=(), attempts=3)``, sleeping on the fake clock."""

    def make(
        base_url: str = BASE, *, token: str | None = None, token_hosts: Collection[str] = (), attempts: int = 3
    ) -> GitHubClient:
        return GitHubClient(
            base_url, token=token, token_hosts=token_hosts, user_agent=USER_AGENT, sleep=clock.sleep, attempts=attempts
        )

    return make


def recorded_list() -> list[dict[str, object]]:
    """The 17 release objects of the ``releases`` recording, as GitHub sent them."""
    data = json.loads((RECORDINGS / "releases" / "list.body").read_bytes())
    assert isinstance(data, list)
    return data
