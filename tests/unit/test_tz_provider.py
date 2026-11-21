from datetime import UTC, datetime, timedelta

import pytest

from recurkit import TimeZoneError
from recurkit.timezones import FakeProvider, FakeZone, LocalTimeKind, Transition

FAKE = FakeProvider()
EE = "Fake/EasternEurope"


def test_fixed_and_half_hour_offsets() -> None:
    assert FAKE.utc_offset("Fake/Plus0530", datetime(2026, 1, 1, tzinfo=UTC)) == timedelta(
        hours=5, minutes=30
    )
    assert FAKE.to_local("Fake/Plus0530", datetime(2026, 1, 1, 20, tzinfo=UTC)) == datetime(
        2026, 1, 2, 1, 30
    )
    assert FAKE.classify("Fake/Plus0530", datetime(2026, 3, 29, 3, 30)) is LocalTimeKind.NORMAL
    assert FAKE.to_local(EE, datetime(2026, 7, 1, 12, tzinfo=UTC)) == datetime(2026, 7, 1, 15)


def test_tz_02_gap_is_shifted_with_offset_before_the_gap() -> None:
    assert FAKE.classify(EE, datetime(2026, 3, 29, 3, 30)) is LocalTimeKind.GAP
    assert not FAKE.exists(EE, datetime(2026, 3, 29, 3, 30))
    resolved = FAKE.resolve(EE, datetime(2026, 3, 29, 3, 30))
    assert resolved.instant == datetime(2026, 3, 29, 1, 30, tzinfo=UTC)
    assert resolved.wall == datetime(2026, 3, 29, 4, 30)
    assert resolved.shifted and resolved.kind is LocalTimeKind.GAP
    assert FAKE.exists(EE, datetime(2026, 3, 29, 4, 0))
    assert FAKE.exists(EE, datetime(2026, 3, 29, 2, 59))


def test_tz_01_fold_refers_to_first_occurrence() -> None:
    local = datetime(2026, 10, 25, 3, 30)
    assert FAKE.classify(EE, local) is LocalTimeKind.FOLD
    assert FAKE.local_offsets(EE, local) == (timedelta(hours=3), timedelta(hours=2))
    resolved = FAKE.resolve(EE, local)
    assert resolved.instant == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert resolved.aware().utcoffset() == timedelta(hours=3)
    assert not resolved.shifted


def test_synthetic_thirty_minute_and_negative_dst_zones() -> None:
    gap = FAKE.resolve("Fake/HalfHour", datetime(2026, 10, 5, 2, 15))
    assert gap.kind is LocalTimeKind.GAP and gap.wall == datetime(2026, 10, 5, 2, 45)
    assert FAKE.classify("Fake/NegativeDST", datetime(2026, 10, 25, 1, 30)) is LocalTimeKind.FOLD
    assert FAKE.classify("Fake/NegativeDST", datetime(2026, 3, 29, 1, 30)) is LocalTimeKind.GAP
    one_shot = FAKE.resolve("Fake/OneShot", datetime(2026, 11, 16, 12, 40))
    assert one_shot.kind is LocalTimeKind.GAP
    assert one_shot.wall == datetime(2026, 11, 16, 13, 55)


def test_tz_04_unknown_zone_raises_time_zone_error() -> None:
    with pytest.raises(TimeZoneError, match="unknown time zone") as info:
        FAKE.utc_offset("Mars/Olympus", datetime(2026, 1, 1, tzinfo=UTC))
    assert info.value.tzid == "Mars/Olympus"
    with pytest.raises(TimeZoneError):
        FAKE.resolve("Fake/UTC", datetime(2026, 1, 1, tzinfo=UTC))
    with pytest.raises(TimeZoneError):
        FAKE.to_local("Fake/UTC", datetime(2026, 1, 1))
    custom = FakeProvider(
        [
            FakeZone(
                "X/Y",
                timedelta(0),
                (Transition(datetime(2026, 1, 1, tzinfo=UTC), timedelta(hours=-1)),),
            )
        ]
    )
    assert custom.zone_names == ("X/Y",)
    assert custom.classify("X/Y", datetime(2025, 12, 31, 23, 30)) is LocalTimeKind.FOLD
