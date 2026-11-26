"""Hand-built ``TlcInvocation`` values for the run-folder tests (package 35): only the fields ``run_folder`` and
the resume command read are meaningful; the rest are placeholders."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from tlaup.java.locate import JavaRuntime, JavaTool
from tlaup.tlc.invocation import TlcInvocation, TlcRequest
from tlaup.versioning.store import Build, Source

COMMIT = "bc1b506" + "0" * 33


def make_build(folder: Path) -> Build:
    return Build(
        id="rolling-1",
        name="rolling",
        commit=COMMIT,
        calver=None,
        built_at=None,
        sha256="0" * 64,
        size=3,
        prerelease=False,
        source=Source("github-release", "https://example.invalid/tla2tools.jar", 1, None, digest_checked=True),
        installed_at="2026-11-15T00:00:00Z",
        capabilities=frozenset(),
        path=folder,
    )


def make_invocation(
    cwd: Path,
    runs: Path,
    *,
    request: TlcRequest | None = None,
    run_id: str = "run0",
    **changes: Any,
) -> TlcInvocation:
    """An invocation for the spec ``<cwd>/Spec.tla``; ``changes`` replace fields, ``extra_args`` also in the
    request, and a ``-metadir`` among them sets ``metadir`` to None as the preflight does."""
    request = request or TlcRequest(spec="Spec.tla", extra_args=tuple(changes.get("extra_args", ())))
    extra = tuple(changes.pop("extra_args", request.extra_args))
    invocation = TlcInvocation(
        request=request,
        build=make_build(cwd / "build"),
        java=JavaRuntime(JavaTool(Path("/usr/bin/java"), "PATH"), "25.0.5", 25, ()),
        spec=cwd / "Spec.tla",
        cfg=None,
        config_arg=None,
        project_root=None,
        cwd=cwd,
        classpath=(),
        tla_library=(),
        override_classes=(),
        warnings=(),
        jvm_options=(),
        workers="1",
        coverage=request.coverage,
        tool_mode=not request.raw,
        suppress_te_spec=False,
        keep=bool(request.keep),
        fp=58 if "-fp" not in extra else None,
        seed=8556987057680880581 if "-seed" not in extra else None,
        extra_args=extra,
        run_id=run_id,
        metadir=None if "-metadir" in extra else runs / run_id,
    )
    return dataclasses.replace(invocation, **changes)
