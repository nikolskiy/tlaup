"""Where tlaup keeps its files: the only code that asks the platform or the environment."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import platformdirs

from tlaup.errors import ConfigInvalid

_APP_NAME = "tlaup"
_HOME = "TLAUP_HOME"
_CONFIG = "TLAUP_CONFIG_DIR"
_CACHE = "TLAUP_CACHE_DIR"
_DATA = "TLAUP_DATA_DIR"


def _folder(name: str, value: str) -> Path:
    path = Path(value)
    if value.startswith("~"):
        path = path.expanduser()
    if not value or not path.is_absolute():
        raise ConfigInvalid(  # noqa: TRY003
            f"{name} must be an absolute path or start with ~, got {value!r}",
            hint=f"set {name} to an absolute folder, or unset it",
        )
    return path


@dataclass(frozen=True)
class AppPaths:
    config: Path
    cache: Path
    data: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppPaths":
        home = _folder(_HOME, env[_HOME]) if _HOME in env else None

        def pick(var: str, sub: str, fallback: str) -> Path:
            if var in env:
                return _folder(var, env[var])
            if home is not None:
                return home / sub
            return Path(fallback)

        return cls(
            config=pick(_CONFIG, "config", platformdirs.user_config_dir(_APP_NAME)),
            cache=pick(_CACHE, "cache", platformdirs.user_cache_dir(_APP_NAME)),
            data=pick(_DATA, "data", platformdirs.user_data_dir(_APP_NAME)),
        )

    @property
    def config_file(self) -> Path:
        return self.config / "config.yaml"

    @property
    def tools(self) -> Path:
        return self.cache / "tool"

    @property
    def pin(self) -> Path:
        return self.cache / "tool" / "pin"

    @property
    def modules(self) -> Path:
        return self.cache / "module"

    @property
    def runs(self) -> Path:
        return self.cache / "runs"

    @property
    def remote(self) -> Path:
        return self.cache / "remote"

    @property
    def java_cache(self) -> Path:
        return self.cache / "java.json"
