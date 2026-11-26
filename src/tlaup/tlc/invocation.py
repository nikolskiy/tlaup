"""The TLC invocation: what the user asked for, and the preflight that decides everything else once (design 20 G1).

`resolve_tlc_invocation` is the preflight of 11 R11, in the order of decision D45: the command line, the spec, the
project root, the cfg, the tool build, Java, then what needs the build. It creates no run folder, starts nothing but
`java -version` (inside `require_java`) and prints nothing: its warnings come back in `TlcInvocation.warnings`.
`PASSTHROUGH` and the checks beside it are the table of 11 R8, the only place such rules live.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC
from typing import TYPE_CHECKING

from tlaup.errors import ConflictingOptions, UsageError
from tlaup.java.classpath import ClasspathResolver
from tlaup.java.locate import require_java
from tlaup.java.opts import jvm_options
from tlaup.modules.registry import Registry
from tlaup.project.core import find_project_root
from tlaup.project.spec import config_arg, resolve_cfg, resolve_spec

if TYPE_CHECKING:
    import random
    from collections.abc import Callable, Mapping, Sequence
    from datetime import datetime
    from pathlib import Path

    from tlaup.config.schema import Settings
    from tlaup.java.locate import JavaRuntime
    from tlaup.paths import AppPaths
    from tlaup.versioning.store import Build

# 11 R8: the flags among TLC's own arguments that tlaup looks at, by exact match, and the tlaup option each one
# conflicts with (None: no tlaup option; the flag only changes what tlaup adds).
PASSTHROUGH: dict[str, str | None] = {
    "-workers": "--workers",
    "-coverage": "--coverage",
    "-config": "--cfg",
    "-metadir": None,
    "-tool": None,
    "-generateSpecTE": None,
    "-noGenerateSpecTE": None,
    "-teSpecOutDir": None,
    "-recover": None,
    "-difftrace": None,
    "-fp": None,
    "-seed": None,
}
TRACE_SPEC_FLAGS = ("-generateSpecTE", "-noGenerateSpecTE", "-teSpecOutDir")

FP_MAX = 130  # -fp is an index into tlc2.util.FP64.Polys, which has 131 entries (11 R6)
SEED_MAX = 2**63 - 1  # TLC reads -seed as a Java long, which is signed
NO_GENERATE_SPEC_TE = "no_generate_spec_te"  # the build capability of decision D36

_WORKERS = re.compile(r"[0-9]+")
_LOCALE_VARIABLES = ("LC_ALL", "LC_CTYPE", "LANG")
_UTF8 = re.compile(r"utf-?8", re.IGNORECASE)
NON_ASCII_HINT = (
    "hint: TLC cannot open a file whose name has non-ASCII characters under the C locale; run with LC_ALL=C.UTF-8"
)


@dataclass(frozen=True)
class TlcRequest:
    """What the user typed, nothing looked up."""

    spec: str
    cfg: str | None = None
    workers: str | None = None  # "auto" or a positive integer, as text; None = take the setting
    coverage: bool = False
    raw: bool = False
    keep: bool | None = None  # --keep; None = take the setting tlc.keep (11 R6, D53)
    java_opts: tuple[str, ...] = ()
    extra_args: tuple[str, ...] = ()  # TLC's own arguments (11 R8)


@dataclass(frozen=True)
class TlcInvocation:
    """Everything decided; no run folder created, nothing started."""

    request: TlcRequest  # kept whole: the resume command is built from it (11 R6)
    build: Build
    java: JavaRuntime
    spec: Path  # absolute, exists, ends in .tla; symbolic links not resolved
    cfg: Path | None  # absolute, exists; None = --cfg was not given
    config_arg: str | None  # what -config is given (11 R4, step 4)
    project_root: Path | None
    cwd: Path  # where tlaup was started (D34)
    classpath: tuple[Path, ...]
    tla_library: tuple[Path, ...]
    override_classes: tuple[str, ...]  # empty until package 34 fills it
    warnings: tuple[str, ...]
    jvm_options: tuple[str, ...]  # settings, then TLAUP_JAVA_OPTS, then --java-opt
    workers: str | None  # None = pass no -workers
    coverage: bool
    tool_mode: bool  # not raw
    suppress_te_spec: bool
    keep: bool
    fp: int | None  # what tlaup passes as -fp; None = the user passed one
    seed: int | None  # the same for -seed
    extra_args: tuple[str, ...]
    run_id: str  # the run folder is paths.runs / run_id
    metadir: Path | None  # None when the user passed -metadir


@dataclass(frozen=True)
class RecoveredRun:
    """The run folder a `-recover PATH` among TLC's arguments points into (11 R6)."""

    run_id: str
    folder: Path  # paths.runs / run_id
    keep: bool  # its run.json says "keep": true or "kept": true
    fp: int | None  # from its run.json, when it has them
    seed: int | None


def new_run_id(now: Callable[[], datetime], rng: random.Random) -> str:
    """ "20261115T100000Z-3fa9c1d2": the UTC start time and eight random hex digits (11 R6)."""
    return f"{now().astimezone(UTC):%Y%m%dT%H%M%SZ}-{rng.getrandbits(32):08x}"


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _read_run_json(folder: Path) -> tuple[bool, int | None, int | None]:
    try:
        data = json.loads((folder / "run.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False, None, None
    if not isinstance(data, dict):
        return False, None, None
    keep = data.get("keep") is True or data.get("kept") is True  # review finding FC1
    return keep, _int_or_none(data.get("fp")), _int_or_none(data.get("seed"))


def find_recovered_run(extra_args: Sequence[str], cwd: Path, runs: Path) -> RecoveredRun | None:
    """The run under `runs` that the word after `-recover` lies in, whether or not that path exists; else None.

    A relative path is read against `cwd`, as TLC reads it, and links are resolved as far as the path exists. A
    run.json that is missing or cannot be read gives keep=False and no values; the run is still returned. Reads
    only; takes no lock.
    """
    args = list(extra_args)
    if "-recover" not in args:
        return None
    index = args.index("-recover")
    if index + 1 >= len(args):
        return None  # TLC reports the missing value
    target = (cwd / args[index + 1]).resolve()  # not strict: resolves what exists, keeps the rest
    try:
        parts = target.relative_to(runs.resolve()).parts
    except ValueError:
        return None
    if not parts:
        return None  # the runs folder itself
    folder = runs / parts[0]
    if not folder.is_dir():
        return None
    keep, fp, seed = _read_run_json(folder)
    return RecoveredRun(parts[0], folder, keep, fp, seed)


def _check_passthrough(request: TlcRequest) -> None:
    """Step 0, the conflicts of the R8 table: a flag among TLC's arguments that a tlaup option also gives."""
    given = {"--workers": request.workers is not None, "--coverage": request.coverage, "--cfg": request.cfg is not None}
    for flag, option in PASSTHROUGH.items():
        if option is not None and given[option] and flag in request.extra_args:
            message = f"{option} and {flag} after -- cannot be used together"
            raise ConflictingOptions(message, hint=f"give {option} or {flag}, not both")


def _check_workers(text: str) -> str:
    """`auto` or a positive integer written in digits; TLC's own looser reading is not taken (11 R8)."""
    if text == "auto" or (_WORKERS.fullmatch(text) is not None and int(text) > 0):
        return text
    message = f"--workers must be auto or a positive integer, not {text!r}"
    raise UsageError(message, hint="use --workers auto or a count such as --workers 4")


def _locale_is_utf8(env: Mapping[str, str]) -> bool:
    for name in _LOCALE_VARIABLES:
        value = env.get(name)
        if value:
            return _UTF8.search(value) is not None
    return False  # nothing set: the C locale


def _path_warnings(spec: Path, cfg: Path | None, env: Mapping[str, str], platform: str) -> tuple[str, ...]:
    """11 R3: a spec or cfg path TLC cannot open, because it is not ASCII and the locale is not UTF-8."""
    if platform.startswith("win") or _locale_is_utf8(env):
        return ()  # on Windows the locale variables do not say what the JVM does
    named = [("spec", spec), ("cfg", cfg)]
    return tuple(
        f"the {kind} path {path} has characters outside ASCII and the locale is not UTF-8\n{NON_ASCII_HINT}"
        for kind, path in named
        if path is not None and not str(path).isascii()
    )


def resolve_tlc_invocation(  # noqa: PLR0913 - the pieces the preflight needs, not the whole context (G1)
    request: TlcRequest,
    *,
    paths: AppPaths,
    settings: Settings,
    env: Mapping[str, str],
    cwd: Path,
    home: Path,
    get_build: Callable[[], Build],
    now: Callable[[], datetime],
    rng: random.Random,
    platform: str = sys.platform,
) -> TlcInvocation:
    """The preflight (11 R11): each step raises a TlaupError and stops; nothing after Java can fail for a reason the
    user caused on the command line."""
    extra = request.extra_args

    # 0. What needs only the command line and the environment.
    _check_passthrough(request)
    requested_workers = None if request.workers is None else _check_workers(request.workers)
    options = jvm_options(settings.java.opts, env, request.java_opts)

    # 1. The spec, and 1b. the project root found from it.
    spec = resolve_spec(request.spec, cwd, platform=platform)
    project_root = find_project_root(spec, home)

    # 2. The cfg, only when --cfg was given (11 R4, step 6).
    cfg = None if request.cfg is None else resolve_cfg(request.cfg, spec, cwd, project_root)
    cfg_text = None if cfg is None else config_arg(cfg, spec, platform=platform)

    # 3. The tool build: the first-run prompt or an install may happen in here, and nothing before it.
    build = get_build()

    # 4. Java.
    java = require_java(env, min_version=settings.java.min_version, cache_file=paths.java_cache)

    # After: nothing here fails for a reason the user caused.
    resolver = ClasspathResolver(
        settings,
        project_root=project_root,
        tool_jar=build.jar,
        module_dirs=[module.path for module in Registry(paths.modules, now=now).list()],
    )
    classpath = tuple(resolver.runtime_classpath(cwd))
    tla_library = tuple(resolver.tla_library(cwd))

    # Package 34: collect_override_classes and check_overrides go here, once the classpath is known.
    override_classes: tuple[str, ...] = ()
    override_warnings: tuple[str, ...] = ()

    warnings = (*java.warnings, *override_warnings, *_path_warnings(spec, cfg, env, platform))

    if "-workers" in extra:
        workers = None
    else:
        workers = requested_workers if requested_workers is not None else str(settings.tlc.workers)

    recovered = find_recovered_run(extra, cwd, paths.runs)
    keep = request.keep if request.keep is not None else settings.tlc.keep
    keep = keep or (recovered is not None and recovered.keep)

    run_id = new_run_id(now, rng)
    fp: int | None = None
    if "-fp" not in extra:
        fp = recovered.fp if recovered is not None and recovered.fp is not None else rng.randint(0, FP_MAX)
    seed: int | None = None
    if "-seed" not in extra:
        seed = recovered.seed if recovered is not None and recovered.seed is not None else rng.randint(0, SEED_MAX)

    return TlcInvocation(
        request=request,
        build=build,
        java=java,
        spec=spec,
        cfg=cfg,
        config_arg=cfg_text,
        project_root=project_root,
        cwd=cwd,
        classpath=classpath,
        tla_library=tla_library,
        override_classes=override_classes,
        warnings=warnings,
        jvm_options=options,
        workers=workers,
        coverage=request.coverage,
        tool_mode=not request.raw,
        suppress_te_spec=NO_GENERATE_SPEC_TE in build.capabilities and not any(f in extra for f in TRACE_SPEC_FLAGS),
        keep=keep,
        fp=fp,
        seed=seed,
        extra_args=extra,
        run_id=run_id,
        metadir=None if "-metadir" in extra else paths.runs / run_id,
    )
