"""The application context: built once per process from the environment."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING

from tlaup.paths import AppPaths
from tlaup.ui import Ui

if TYPE_CHECKING:
    from tlaup.config.schema import Settings


@dataclass(frozen=True)
class AppContext:
    paths: AppPaths
    env: Mapping[str, str]
    debug: bool
    ui: Ui

    @cached_property
    def settings(self) -> "Settings":
        """The settings, loaded on first use; each warning is printed once, here (design 14 F1).

        A broken file raises `ConfigInvalid` every time this is asked for, since nothing is cached then.
        """
        from tlaup.config.loader import load_settings  # noqa: PLC0415

        loaded = load_settings(self.paths, self.env)
        for warning in loaded.warnings:
            self.ui.warning(warning)
        return loaded.settings


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
