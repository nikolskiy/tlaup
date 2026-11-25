"""The application context: built once per process from the environment."""

import os
from collections.abc import Mapping
from dataclasses import dataclass

from tlaup.paths import AppPaths
from tlaup.ui import Ui


@dataclass(frozen=True)
class AppContext:
    paths: AppPaths
    env: Mapping[str, str]
    debug: bool
    ui: Ui
    # settings: added by package 19


_cache: list[AppContext] = []


def get_context() -> AppContext:
    """Return the process-wide context, building it from `os.environ` on the first call."""
    if not _cache:
        env = dict(os.environ)
        _cache.append(
            AppContext(paths=AppPaths.from_env(env), env=env, debug=env.get("TLAUP_DEBUG") == "1", ui=Ui.for_process())
        )
    return _cache[0]


def build_context(env: Mapping[str, str], *, debug: bool) -> AppContext:
    """Build the context of this run of the app and make it the cached one (the root callback's, design 14 F10).

    `debug` is the `--debug` flag; `TLAUP_DEBUG=1` in `env` switches it on as well. Raises `ConfigInvalid` from
    `AppPaths.from_env`; the cache is then empty, not left holding an earlier run's context.
    """
    _cache.clear()
    env = dict(env)
    built = AppContext(
        paths=AppPaths.from_env(env),
        env=env,
        debug=debug or env.get("TLAUP_DEBUG") == "1",
        ui=Ui.for_process(),
    )
    _cache.append(built)
    return built


def reset() -> None:
    """Forget the cached context; for tests."""
    _cache.clear()
