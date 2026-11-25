"""The application context: built once per process from the environment."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from tlaup.paths import AppPaths


@dataclass(frozen=True)
class AppContext:
    paths: AppPaths
    env: Mapping[str, str]
    debug: bool
    # ui: added by package 16; settings: added by package 19


_cache: list[AppContext] = []


def get_context() -> AppContext:
    """Return the process-wide context, building it from `os.environ` on the first call."""
    if not _cache:
        env = dict(os.environ)
        _cache.append(AppContext(paths=AppPaths.from_env(env), env=env, debug=env.get("TLAUP_DEBUG") == "1"))
    return _cache[0]


def reset() -> None:
    """Forget the cached context; for tests."""
    _cache.clear()
