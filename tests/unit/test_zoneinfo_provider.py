from datetime import UTC, datetime, timedelta

import pytest

from recurkit import TimeZoneError
from recurkit.timezones import LocalTimeKind, ZoneInfoProvider

ZI = ZoneInfoProvider()


def test_kyiv_spring_gap_and_autumn_fold() -> None:
    gap = ZI.resolve("Europe/Kyiv", datetime(2026, 3, 29, 3, 30))
    assert gap.kind is LocalTimeKind.GAP
    assert gap.wall == datetime(2026, 3, 29, 4, 30)
    fold = ZI.resolve("Europe/Kyiv", datetime(2026, 10, 25, 3, 30))
    assert fold.kind is LocalTimeKind.FOLD
    assert fold.instant == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)


def test_tz_02_new_york_example_from_rfc() -> None:
    # RFC 5545, 3.3.5: TZID=America/New_York:20070311T023000 is 03:30 EDT.
    resolved = ZI.resolve("America/New_York", datetime(2007, 3, 11, 2, 30))
    assert resolved.wall == datetime(2007, 3, 11, 3, 30)
    assert resolved.offset == timedelta(hours=-4)


def test_tz_01_new_york_fold_example_from_rfc() -> None:
    # RFC 5545, 3.3.5: TZID=America/New_York:20071104T013000 is 01:30 EDT (UTC-04:00).
    resolved = ZI.resolve("America/New_York", datetime(2007, 11, 4, 1, 30))
    assert resolved.kind is LocalTimeKind.FOLD
    assert resolved.offset == timedelta(hours=-4)


def test_sydney_and_india() -> None:
    # Sydney (southern hemisphere): clocks go forward on the first Sunday of October.
    assert ZI.classify("Australia/Sydney", datetime(2026, 10, 4, 2, 30)) is LocalTimeKind.GAP
    assert ZI.classify("Australia/Sydney", datetime(2026, 4, 5, 2, 30)) is LocalTimeKind.FOLD
    india = ZI.resolve("Asia/Kolkata", datetime(2026, 3, 29, 2, 30))
    assert india.kind is LocalTimeKind.NORMAL
    assert india.offset == timedelta(hours=5, minutes=30)


@pytest.mark.parametrize("tzid", ["Mars/Olympus", "", "../etc/passwd", "Europe/"])
def test_tz_04_unknown_zone_is_time_zone_error(tzid: str) -> None:
    assert not ZI.has_zone(tzid)
    with pytest.raises(TimeZoneError):
        ZI.utc_offset(tzid, datetime(2026, 1, 1, tzinfo=UTC))
