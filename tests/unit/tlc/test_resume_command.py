"""The resume command, the note and the reminder of a kept run folder (design 11 R6; package 35).

Hand-built ``TlcInvocation`` and ``Kept`` values; the zone of the note's clock time is passed in.
"""

from __future__ import annotations

import shlex
import subprocess
from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest

from tests.unit.tlc.invocations import make_invocation
from tlaup.tlc.invocation import TlcRequest
from tlaup.tlc.rundirs import Kept, KeptSummary, format_size, kept_note, reminder, resume_command

if TYPE_CHECKING:
    from pathlib import Path

    from tlaup.tlc.invocation import TlcInvocation

ENDED = datetime(2026, 11, 15, 16, 15, tzinfo=UTC)


@pytest.fixture
def cwd(tmp_path: Path) -> Path:
    return tmp_path / "work"


def invocation(cwd: Path, request: TlcRequest, **changes: object) -> TlcInvocation:
    return make_invocation(cwd, cwd / "runs", request=request, extra_args=request.extra_args, **changes)


def words(inv: TlcInvocation, checkpoint: Path, *, workers_reported: int | None = None) -> list[str]:
    return shlex.split(resume_command(inv, checkpoint, fp=58, seed=7, workers_reported=workers_reported, windows=False))


def test_the_spec_and_cfg_come_out_absolute_and_keep_is_there(cwd: Path) -> None:
    request = TlcRequest(spec="Spec.tla", cfg="models/Small.cfg", extra_args=("-deadlock",))
    inv = invocation(cwd, request, cfg=cwd / "models" / "Small.cfg")
    checkpoint = cwd / "runs" / "run0" / "states"
    assert words(inv, checkpoint) == [
        "tlaup",
        "tlc",
        str(cwd / "Spec.tla"),
        "--cfg",
        str(cwd / "models" / "Small.cfg"),
        "--keep",
        "--",
        "-deadlock",
        "-fp",
        "58",
        "-seed",
        "7",
        "-recover",
        str(checkpoint),
    ]


def test_no_cfg_when_none_was_given(cwd: Path) -> None:
    inv = invocation(cwd, TlcRequest(spec="Spec.tla"), cfg=cwd / "Spec.cfg")
    assert "--cfg" not in words(inv, cwd / "states")


def test_the_options_of_the_request_are_carried_in_order(cwd: Path) -> None:
    request = TlcRequest(
        spec="Spec.tla", workers="4", coverage=True, raw=True, java_opts=("-Xmx4g", "-Dx=a b"), extra_args=()
    )
    inv = invocation(cwd, request, workers="4")
    assert words(inv, cwd / "states")[3:10] == [
        "--keep",
        "--workers",
        "4",
        "--coverage",
        "--raw",
        "--java-opt=-Xmx4g",
        "--java-opt=-Dx=a b",
    ]


def test_workers_from_the_settings_are_not_carried_unless_the_start_line_reported_a_count(cwd: Path) -> None:
    inv = invocation(cwd, TlcRequest(spec="Spec.tla"), workers="8")
    assert "--workers" not in words(inv, cwd / "states")
    assert words(inv, cwd / "states", workers_reported=6)[3:6] == ["--keep", "--workers", "6"]


def test_the_reported_count_wins_over_the_command_line(cwd: Path) -> None:
    inv = invocation(cwd, TlcRequest(spec="Spec.tla", workers="auto"), workers="auto")
    assert words(inv, cwd / "states", workers_reported=12)[3:6] == ["--keep", "--workers", "12"]
    assert words(inv, cwd / "states")[3:6] == ["--keep", "--workers", "auto"]


def test_a_workers_among_tlc_arguments_stays_there(cwd: Path) -> None:
    inv = invocation(cwd, TlcRequest(spec="Spec.tla", extra_args=("-workers", "3")), workers=None)
    result = words(inv, cwd / "states", workers_reported=3)
    assert "--workers" not in result
    assert result[result.index("--") + 1 : result.index("--") + 3] == ["-workers", "3"]


def test_recover_fp_and_seed_among_tlc_arguments_are_replaced_not_doubled(cwd: Path) -> None:
    request = TlcRequest(
        spec="Spec.tla",
        extra_args=("-recover", "old/states", "-fp", "3", "-deadlock", "-seed", "9", "-checkpoint", "1"),
    )
    inv = invocation(cwd, request)
    result = words(inv, cwd / "runs" / "old" / "states")
    assert result[result.index("--") :] == [
        "--",
        "-deadlock",
        "-checkpoint",
        "1",
        "-fp",
        "58",
        "-seed",
        "7",
        "-recover",
        str(cwd / "runs" / "old" / "states"),
    ]


def test_auto_install_and_the_environment_are_left_out(cwd: Path) -> None:
    inv = invocation(cwd, TlcRequest(spec="Spec.tla"))
    assert "--auto-install" not in words(inv, cwd / "states")


def test_on_windows_the_join_is_list2cmdline(cwd: Path) -> None:
    request = TlcRequest(spec="Spec.tla", java_opts=("-Dx=a b",))
    inv = invocation(cwd, request)
    checkpoint = cwd / "states"
    posix = words(inv, checkpoint)
    windows = resume_command(inv, checkpoint, fp=58, seed=7, workers_reported=None, windows=True)
    assert windows == subprocess.list2cmdline(posix)


def test_no_fp_or_seed_when_run_json_has_none(cwd: Path) -> None:
    inv = invocation(cwd, TlcRequest(spec="Spec.tla"))
    result = shlex.split(resume_command(inv, cwd / "states", fp=None, seed=None, workers_reported=None))
    assert "-fp" not in result
    assert "-seed" not in result


# ---------------------------------------------------------------------- the note


def kept(tmp_path: Path, reason: str, *, checkpoint_at: datetime) -> Kept:
    folder = tmp_path / "runs" / "20261115T100000Z-3fa9c1d2"
    return Kept(
        path=folder,
        checkpoint_dir=folder / "states",
        size=2_100_000_000,
        stopped_after=timedelta(hours=2, minutes=13),
        checkpoint_at=checkpoint_at,
        reason=reason,
        ended=ENDED,
        resume_command="tlaup tlc /specs/Spec.tla --keep -- -fp 58 -seed 7 -recover /runs/x/states",
    )


@pytest.mark.parametrize("reason", ["interrupted", "tlaup failed", "TLC crashed (exit 255)"])
def test_the_note_has_two_lines(tmp_path: Path, reason: str) -> None:
    value = kept(tmp_path, reason, checkpoint_at=datetime(2026, 11, 15, 14, 2, tzinfo=UTC))
    assert kept_note(value, zone=UTC) == (
        f"Checkpoint kept (2.1 GB, {reason} after 2 h 13 min, checkpoint of 14:02): {value.path}",
        "Resume with: tlaup tlc /specs/Spec.tla --keep -- -fp 58 -seed 7 -recover /runs/x/states",
    )


def test_the_checkpoint_time_is_in_the_given_zone(tmp_path: Path) -> None:
    value = kept(tmp_path, "interrupted", checkpoint_at=datetime(2026, 11, 15, 14, 2, tzinfo=UTC))
    first, _ = kept_note(value, zone=timezone(timedelta(hours=1)))
    assert "checkpoint of 15:02)" in first


def test_a_checkpoint_of_another_day_names_its_date(tmp_path: Path) -> None:
    value = kept(tmp_path, "interrupted", checkpoint_at=datetime(2026, 11, 14, 23, 50, tzinfo=UTC))
    first, _ = kept_note(value, zone=UTC)
    assert "checkpoint of 2026-11-14 23:50)" in first


def test_the_day_is_the_one_in_the_zone(tmp_path: Path) -> None:
    value = kept(tmp_path, "interrupted", checkpoint_at=datetime(2026, 11, 14, 23, 50, tzinfo=UTC))
    first, _ = kept_note(value, zone=timezone(timedelta(hours=2)))  # 01:50 on the 15th, the day it ended
    assert "checkpoint of 01:50)" in first


def test_a_kept_value_without_a_command_has_no_note(tmp_path: Path) -> None:
    value = kept(tmp_path, "interrupted", checkpoint_at=ENDED)
    with pytest.raises(ValueError, match="no resume command"):
        kept_note(Kept(**{**value.__dict__, "resume_command": None}))


# ---------------------------------------------------------------------- the reminder and the sizes


def test_the_reminder_singular_and_plural() -> None:
    assert reminder(KeptSummary(1, 2_100_000_000)) == "1 kept run folder holds 2.1 GB (tlaup cache list)"
    assert reminder(KeptSummary(3, 7_400_000_000)) == "3 kept run folders hold 7.4 GB (tlaup cache list)"


@pytest.mark.parametrize(
    ("size", "text"),
    [
        (0, "0 B"),
        (999, "999 B"),
        (1000, "1.0 kB"),
        (1_500, "1.5 kB"),
        (1_250, "1.3 kB"),
        (2_250_000_000, "2.3 GB"),
        (29_000_000, "29.0 MB"),
        (2_149_999_999, "2.1 GB"),
        (999_960, "1.0 MB"),
        (3_200_000_000_000, "3.2 TB"),
        (5_000_000_000_000_000, "5000.0 TB"),
    ],
)
def test_format_size_units(size: int, text: str) -> None:
    assert format_size(size) == text
