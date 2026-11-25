"""What the `module` commands build the same way. Nothing heavy is imported at the top (design 14 F9)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tlaup.context import AppContext
    from tlaup.modules.registry import Registry


def open_registry(ctx: AppContext) -> Registry:
    """The registry of ``<cache>/module`` with the real clock; reads no setting."""
    from tlaup.cmd.tool._shared import utc_now
    from tlaup.modules.registry import Registry

    return Registry(ctx.paths.modules, now=utc_now)
