from pathlib import Path

from tlaup.config.loader import cache_dir


def get_modules_dir() -> Path:
    return cache_dir() / "modules"


def get_run_dir() -> Path:
    return cache_dir() / "run"


def get_tlc_run_dir() -> Path:
    return get_run_dir() / "tlc"
