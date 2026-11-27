"""The injected time of design 01 T4."""

from datetime import UTC, datetime, timedelta, timezone

import pytest

from tests.clock import FakeClock


def test_starts_at_the_fixed_time() -> None:
    clock = FakeClock()
    assert clock.now() == datetime(2026, 11, 15, tzinfo=UTC)
    assert clock() == datetime(2026, 11, 15, tzinfo=UTC).timestamp()
    assert clock.sleeps == []


def test_sleep_records_and_advances() -> None:
    clock = FakeClock()
    before = clock()
    clock.sleep(1.5)
    clock.sleep(30)
    assert clock.sleeps == [1.5, 30]
    assert clock() == before + 31.5
    assert clock.now() == datetime(2026, 11, 15, tzinfo=UTC) + timedelta(seconds=31.5)


def test_now_is_aware_utc_and_moves_with_advance() -> None:
    clock = FakeClock(datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=2))))
    assert clock.now().tzinfo is UTC
    assert clock.now() == datetime(2026, 1, 1, 10, tzinfo=UTC)
    clock.advance(3600)
    assert clock.now() == datetime(2026, 1, 1, 11, tzinfo=UTC)
    assert clock.sleeps == []


def test_refuses_a_naive_start_and_going_back() -> None:
    with pytest.raises(ValueError, match="aware"):
        FakeClock(datetime(2026, 1, 1))  # noqa: DTZ001 - a naive start is the input under test
    with pytest.raises(ValueError, match="back"):
        FakeClock().advance(-1)
