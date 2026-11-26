from datetime import datetime

from rich.align import Align
from rich.console import Group
from rich.table import Table
from rich.text import Text

from tlaup.tlc.models import CheckState, ModelCheckResult


class LogDeduplicator:
    """Groups consecutive identical logs into a single line with a count badge."""

    def __init__(self) -> None:
        self.last_line: str | None = None
        self.count: int = 1

    def process(self, line: str) -> str:
        stripped_line = line.strip()
        if stripped_line == self.last_line:
            self.count += 1
            return f"{stripped_line} ({self.count})"

        self.last_line = stripped_line
        self.count = 1
        return stripped_line


class HeaderComponent:
    """Renders the TLC start header."""

    def __init__(self, tlc_version: str = "unknown") -> None:
        self.tlc_version = tlc_version

    def render(self, _result: ModelCheckResult) -> Text:
        return Text(
            f"Starting TLC model checker (version {self.tlc_version}).",
            style="bold",
        )


class StatusInfoComponent:
    """Renders detailed status info (clock, state, Ctrl+C prompt)."""

    def render(self, result: ModelCheckResult) -> Group:
        status_text = result.status.name
        if result.state == CheckState.Stopped:
            status_text = "canceled"

        if not result.start_date_time:
            elapsed_str = "00:00:00"
            elapsed_style = "dim"
        else:
            if result.state == CheckState.Running:
                elapsed = datetime.now() - result.start_date_time
            else:
                elapsed = (result.end_date_time or datetime.now()) - result.start_date_time
            seconds = int(elapsed.total_seconds())
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            elapsed_str = f"{hours:02}:{minutes:02}:{seconds:02}"
            elapsed_style = "bold cyan"

        info_text = Text()
        info_text.append(f"Elapsed time: {elapsed_str}\n", style=elapsed_style)
        info_text.append(f"Status: {status_text}\n")

        if result.state == CheckState.Running:
            info_text.append("Stop with Ctrl + C", style="yellow")

        return Group(Align.center(Text("Status Info", style="bold")), info_text)


class LogsComponent:
    """Renders a window of deduplicated log lines."""

    def __init__(self, limit: int | None = 10) -> None:
        self.limit = limit

    def render(self, result: ModelCheckResult) -> Group:
        deduped_logs: list[str] = []
        temp_dedup = LogDeduplicator()
        for line in result.output_lines:
            processed = temp_dedup.process(line)
            if temp_dedup.count > 1 and deduped_logs:
                deduped_logs[-1] = processed
            else:
                deduped_logs.append(processed)

        log_lines = Text()
        items = deduped_logs
        if self.limit is not None and len(items) > self.limit:
            items = items[-self.limit :]

        for line in items:
            log_lines.append(f"{line}\n")

        return Group(Align.center(Text("TLC instance info", style="bold")), log_lines)


class StatsTableComponent:
    """Renders the State Space Progress table, optionally limited to last N items."""

    def __init__(self, limit: int | None = None) -> None:
        self.limit = limit

    def render(self, result: ModelCheckResult) -> Table:
        table = Table(title="State Space Progress", expand=True)
        table.add_column("Time")
        table.add_column("Diameter", justify="right")
        table.add_column("Found", justify="right")
        table.add_column("Distinct", justify="right")
        table.add_column("Queue", justify="right")

        items = result.initial_states_stat
        if self.limit is not None and len(items) > self.limit:
            items = items[-self.limit :]

        for item in items:
            table.add_row(
                item.timestamp,
                str(item.diameter),
                f"{item.total:,}",
                f"{item.distinct:,}",
                f"{item.queue_size:,}",
            )
        return table
