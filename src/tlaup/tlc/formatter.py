from dataclasses import dataclass, field
from typing import Any

from rich.console import Group
from rich.layout import Layout
from rich.text import Text

from tlaup.tlc.components import (
    HeaderComponent,
    LogsComponent,
    StatsTableComponent,
    StatusInfoComponent,
)
from tlaup.tlc.models import ModelCheckResult


@dataclass
class _Section:
    """A named section in the TLC display."""

    name: str
    renderable: Any = field(default_factory=lambda: Text(""))
    size: int | None = None

    def update(self, renderable: Any) -> None:
        """Update the section content."""
        self.renderable = renderable

    def __rich__(self) -> Any:
        return self.renderable


class TlcDisplay:
    """A dynamic display that grows as content is added."""

    def __init__(self) -> None:
        self.children: list[_Section] = []
        self.renderable: Any = Text("")

    def __getitem__(self, name: str) -> _Section:
        for child in self.children:
            if child.name == name:
                return child
        raise KeyError(name)

    def update(self, renderable: Any) -> None:
        """Update root renderable (used before splitting)."""
        self.renderable = renderable

    def split_column(self, *sections: _Section) -> None:
        """Set the active sections."""
        self.children = list(sections)

    def __rich__(self) -> Group:
        if not self.children:
            return Group(self.renderable)
        return Group(*self.children)


class TlcFormatter:
    """Generates Rich layout for TLC model checking."""

    def __init__(self, tlc_version: str = "unknown") -> None:
        self.tlc_version = tlc_version
        self.header_comp = HeaderComponent(tlc_version)
        self.status_info_comp = StatusInfoComponent()
        self.logs_comp = LogsComponent(limit=10)
        self.stats_comp = StatsTableComponent()

    def create_layout(self) -> Any:
        """Create the initial layout structure with only the header."""
        layout = TlcDisplay()
        layout.update(self.header_comp.render(ModelCheckResult()))
        return layout

    def update(self, layout: Any, result: ModelCheckResult) -> None:
        """Main update entry point that manages layout structure and content."""
        self._ensure_layout_structure(layout, result)
        self.update_header(layout, result)
        if self._has_child(layout, "clock"):
            self.update_clock(layout, result)
        if self._has_child(layout, "logs"):
            self.update_logs(layout, result)
        if self._has_child(layout, "stats"):
            self.update_stats(layout, result)

    def _has_child(self, layout: Any, name: str) -> bool:
        """Check if a layout has a child with the given name."""
        return any(child.name == name for child in layout.children)

    def _ensure_layout_structure(self, layout: Any, result: ModelCheckResult) -> None:
        """Dynamically add sections as data becomes available."""
        has_logs = bool(result.output_lines)
        has_stats = bool(result.initial_states_stat)
        has_clock = bool(result.start_date_time or result.process_info or result.duration)

        # Build expected structure in desired order:
        # 1. Header
        # 2. Status Info (clock)
        # 3. TLC instance info (logs)
        # 4. State Space Progress (stats) - grows infinitely at the bottom
        new_layouts = [_Section(name="header", size=2)]
        if has_clock:
            new_layouts.append(_Section(name="clock", size=7))
        if has_logs:
            new_layouts.append(_Section(name="logs"))
        if has_stats:
            new_layouts.append(_Section(name="stats"))

        # Check if we need to update
        current_names = [lay.name for lay in layout.children]
        expected_names = [lay.name for lay in new_layouts]

        if current_names != expected_names:
            layout.split_column(*new_layouts)

    def update_header(self, layout: Any, result: ModelCheckResult) -> None:
        """Update header."""
        header_text = self.header_comp.render(result)
        if self._has_child(layout, "header"):
            layout["header"].update(header_text)
        else:
            layout.update(header_text)

    def update_stats(self, layout: Layout, result: ModelCheckResult) -> None:
        table = self.stats_comp.render(result)
        layout["stats"].update(table)

    def update_logs(self, layout: Layout, result: ModelCheckResult) -> None:
        """Update logs panel with TLC output."""
        group = self.logs_comp.render(result)
        layout["logs"].update(group)

    def update_clock(self, layout: Layout, result: ModelCheckResult) -> None:
        """Update info panel at the bottom with clock and TLC stats."""
        layout["clock"].update(StatusInfoRenderable(result))


class StatusInfoRenderable:
    """Renderable that computes elapsed time dynamically."""

    def __init__(self, result: ModelCheckResult) -> None:
        self.result = result

    def __rich__(self) -> Group:
        """Render the status info group."""
        comp = StatusInfoComponent()
        return comp.render(self.result)
