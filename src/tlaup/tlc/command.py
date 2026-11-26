"""The TLC command line, built from a TlcInvocation: the only place its flags are assembled (design 20 G1).

    <java> [-javaagent:<lifeline jar>=pid=<tlaup's pid>] -Dfile.encoding=UTF-8 -Dstdout.encoding=UTF-8
           -Dstderr.encoding=UTF-8 <jvm options> -DTLA-Library=<dirs> [-Dtlc2.overrides.TLCOverrides=<classes>]
           -cp <classpath> tlc2.TLC
           [-tool] [-metadir <dir>] [-noGenerateSpecTE] [-workers <w>] [-coverage 1] [-fp <n>] [-seed <n>]
           [-config <cfg>] <extra args> <absolute spec>

The lifeline and the three encoding options are added by `JavaInvocation.argv()` (decisions D51 and D56), not here.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from tlaup.java.launcher import JavaInvocation

if TYPE_CHECKING:
    from tlaup.tlc.invocation import TlcInvocation

# Until package 41 creates tlaup.tools.ENTRY_POINTS and replaces it (21 S4).
TLC_MAIN_CLASS = "tlc2.TLC"
TLA_LIBRARY_PROPERTY = "TLA-Library"
OVERRIDES_PROPERTY = "tlc2.overrides.TLCOverrides"


def build_tlc_command(inv: TlcInvocation) -> JavaInvocation:
    """The Java command of a TLC run. Pure: reads no disk and no environment; `cwd` stays None (D34)."""
    properties: list[tuple[str, str]] = []
    if inv.tla_library:
        properties.append((TLA_LIBRARY_PROPERTY, os.pathsep.join(str(folder) for folder in inv.tla_library)))
    if inv.override_classes:
        properties.append((OVERRIDES_PROPERTY, os.pathsep.join(inv.override_classes)))

    args: list[str] = []
    if inv.tool_mode:
        args.append("-tool")
    if inv.metadir is not None:
        args.extend(("-metadir", str(inv.metadir)))
    if inv.suppress_te_spec:
        args.append("-noGenerateSpecTE")
    if inv.workers is not None:
        args.extend(("-workers", inv.workers))
    if inv.coverage:
        args.extend(("-coverage", "1"))
    if inv.fp is not None:
        args.extend(("-fp", str(inv.fp)))
    if inv.seed is not None:
        args.extend(("-seed", str(inv.seed)))
    if inv.config_arg is not None:
        args.extend(("-config", inv.config_arg))
    args.extend(inv.extra_args)
    args.append(str(inv.spec))

    return JavaInvocation(
        java=inv.java.tool.path,
        jvm_options=inv.jvm_options,
        system_properties=tuple(properties),
        classpath=inv.classpath,
        main_class=TLC_MAIN_CLASS,
        args=tuple(args),
    )
