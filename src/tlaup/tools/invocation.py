"""The invocation of the tools that are not TLC: ``sany``, ``pcal`` and ``repl`` (design 21, head, and S1).

`resolve_tool_invocation` is the preflight of 11 R11 for them, on the same steps in the same order as
`resolve_tlc_invocation` (decision D45): the command line, the spec, the tool build, whether the build can run the
tool, then Java. It starts nothing but `java -version` (inside `require_java`) and prints nothing; its warnings come
back in `ToolInvocation.warnings`. `build_tool_command` is pure.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from tlaup.errors import ToolNotInBuild, UsageError
from tlaup.java.classpath import run_paths
from tlaup.java.launcher import JavaInvocation
from tlaup.java.locate import require_java
from tlaup.java.opts import env_options, jvm_options
from tlaup.project.core import find_project_root
from tlaup.project.spec import resolve_spec
from tlaup.tools import ENTRY_POINTS
from tlaup.versioning.spec import format_build

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from datetime import datetime
    from pathlib import Path

    from tlaup.config.schema import Settings
    from tlaup.java.locate import JavaRuntime
    from tlaup.paths import AppPaths
    from tlaup.versioning.store import Build

Tool = Literal["sany", "pcal", "repl"]

# The capability a tool needs of the build (00, "What a build can do"); a tool missing here needs none.
REQUIRED_CAPABILITY: Mapping[Tool, str] = {"repl": "repl"}

TLA_LIBRARY_PROPERTY = "TLA-Library"
SPEC_TOOLS: tuple[Tool, ...] = ("sany", "pcal")  # the tools that read a spec, in the spec's folder
EXPLORER_FLAG = "-d"  # SANY's interactive explorer, exactly (S1, step 7)


@dataclass(frozen=True)
class ToolInvocation:
    """Everything decided; nothing started."""

    build: Build
    java: JavaRuntime
    main_class: str
    spec: Path | None  # resolve_spec's result; None for repl
    cwd: Path | None  # the spec's folder for sany and pcal; None (do not change folder) for repl
    classpath: tuple[Path, ...]
    tla_library: tuple[Path, ...]
    jvm_options: tuple[str, ...]
    args: tuple[str, ...]  # the tool's own arguments, after `--`, as typed; the spec is not among them
    warnings: tuple[str, ...]  # from finding Java (13 J2, J3)


def _check_explorer(extra_args: Sequence[str]) -> None:
    """S1, step 7: exactly the argument ``-d``, which waits for input tlaup does not give; nothing looser, since SANY
    refuses grouped flags such as ``-dl`` and ``-ls`` itself."""
    if EXPLORER_FLAG in extra_args:
        message = "-d starts SANY's interactive explorer, which waits for input that tlaup does not give it"
        hint = "run it with Java directly, on the jar that `tlaup tool path` prints"
        raise UsageError(message, hint=hint)


def _check_capability(tool: Tool, build: Build) -> None:
    """Step 3b: a fact about the build, so Java is not started, not even for its version."""
    needed = REQUIRED_CAPABILITY.get(tool)
    if needed is not None and needed not in build.capabilities:
        message = f"the pinned build {format_build(build)} has no {tool.upper()}"
        raise ToolNotInBuild(message, hint="install a rolling build: `tlaup tool install rolling`")


def check_command_line(tool: Tool, extra_args: Sequence[str], env: Mapping[str, str]) -> None:
    """Step 0 of 11 R11: what needs only the command line and the environment; reads nothing from the disk.

    The command calls it before it loads the settings, so a broken config file (3) never hides a mistake typed on
    the command line (2).
    """
    env_options(env)  # only the quoting of TLAUP_JAVA_OPTS; the setting java.opts is read after this step
    if tool == "sany":
        _check_explorer(extra_args)


def resolve_tool_invocation(  # noqa: PLR0913 - the pieces the preflight needs, not the whole context (21)
    tool: Tool,
    spec: str | None,
    *,
    java_opts: Sequence[str],
    extra_args: Sequence[str],
    paths: AppPaths,
    settings: Settings,
    env: Mapping[str, str],
    cwd: Path,
    home: Path,
    now: Callable[[], datetime],
    get_build: Callable[[], Build],
) -> ToolInvocation:
    """The preflight (11 R11): each step raises a TlaupError and stops; nothing after Java can fail for a reason the
    user caused on the command line."""
    # 0. What needs only the command line and the environment.
    check_command_line(tool, extra_args, env)
    options = jvm_options(settings.java.opts, env, java_opts)

    # 1. The spec, and 1b. the project root found from it. There is no step 2: these tools take no cfg.
    spec_path: Path | None = None
    project_root: Path | None = None
    if tool in SPEC_TOOLS:
        if spec is None:
            message = f"{tool} needs a SPEC"
            raise UsageError(message)
        spec_path = resolve_spec(spec, cwd)
        if tool == "sany":
            project_root = find_project_root(spec_path, home)

    # 3. The tool build: the first-run prompt or an install may happen in here, and nothing before it.
    build = get_build()
    _check_capability(tool, build)  # 3b

    # 4. Java.
    java = require_java(env, min_version=settings.java.min_version, cache_file=paths.java_cache)

    # After: nothing here fails for a reason the user caused.
    classpath: tuple[Path, ...] = (build.jar,)  # pcal: the jar alone, no library folders
    tla_library: tuple[Path, ...] = ()
    if tool != "pcal":
        classpath, tla_library = run_paths(
            settings, project_root=project_root, tool_jar=build.jar, modules=paths.modules, now=now, cwd=cwd
        )
    return ToolInvocation(
        build=build,
        java=java,
        main_class=ENTRY_POINTS[tool],
        spec=spec_path,
        cwd=None if spec_path is None else spec_path.parent,
        classpath=classpath,
        tla_library=tla_library,
        jvm_options=options,
        args=tuple(extra_args),
        warnings=java.warnings,
    )


def build_tool_command(inv: ToolInvocation) -> JavaInvocation:
    """The Java command of a tool run. Pure: reads no disk and no environment. The spec's file name is last."""
    properties: tuple[tuple[str, str], ...] = ()
    if inv.tla_library:
        properties = ((TLA_LIBRARY_PROPERTY, os.pathsep.join(str(folder) for folder in inv.tla_library)),)
    args = inv.args if inv.spec is None else (*inv.args, inv.spec.name)
    return JavaInvocation(
        java=inv.java.tool.path,
        jvm_options=inv.jvm_options,
        system_properties=properties,
        classpath=inv.classpath,
        main_class=inv.main_class,
        args=args,
        cwd=inv.cwd,
    )
