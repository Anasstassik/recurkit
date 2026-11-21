from datetime import UTC, date, datetime, timedelta

import pytest

from recurkit import TimeZoneError
from recurkit.timezones import FakeProvider, LocalTimeKind, parse_posix_tz
from recurkit.timezones.posix import PosixDate, parse_posix_time


def test_parse_offsets_names_and_default_rules() -> None:
    kyiv = parse_posix_tz("Kyiv", "EET-2EEST,M3.5.0/3,M10.5.0/4")
    assert (kyiv.standard, kyiv.daylight) == (timedelta(hours=2), timedelta(hours=3))
    assert kyiv.switches(2026) == (
        datetime(2026, 3, 29, 1, tzinfo=UTC),
        datetime(2026, 10, 25, 1, tzinfo=UTC),
    )
    india = parse_posix_tz("India", "IST-5:30")
    assert india.offset_at(datetime(2026, 6, 1, tzinfo=UTC)) == timedelta(hours=5, minutes=30)
    quoted = parse_posix_tz("LordHowe", "<+1030>-10:30<+11>-11,M10.1.0,M4.1.0")
    assert quoted.daylight == timedelta(hours=11)
    implicit = parse_posix_tz("X", "AAA3BBB,M3.2.0,M11.1.0")  # DST one hour ahead by default
    assert implicit.daylight == timedelta(hours=-2)
    assert parse_posix_time("-1:02:03") == -timedelta(hours=1, minutes=2, seconds=3)
    assert parse_posix_time("+167") == timedelta(hours=167)


def test_julian_and_zero_based_day_rules() -> None:
    assert PosixDate("J60").in_year(2024) == date(2024, 3, 1)  # February 29 is never counted
    assert PosixDate("59").in_year(2024) == date(2024, 2, 29)  # zero-based, counts February 29
    assert PosixDate("M2.5.0").in_year(2026) == date(2026, 2, 22)  # week 5 = last Sunday
    with pytest.raises(TimeZoneError):
        PosixDate("365").in_year(2026)


def test_southern_and_negative_daylight_time() -> None:
    fake = FakeProvider([])
    fake.add_posix("Sydney", "AEST-10AEDT,M10.1.0,M4.1.0/3")
    assert fake.utc_offset("Sydney", datetime(2026, 1, 15, tzinfo=UTC)) == timedelta(hours=11)
    assert fake.utc_offset("Sydney", datetime(2026, 7, 15, tzinfo=UTC)) == timedelta(hours=10)
    # Europe/Dublin: IST (+1) is the standard time, GMT (0) the "daylight" time in winter.
    fake.add_posix("Dublin", "IST-1GMT0,M10.5.0,M3.5.0/1")
    assert fake.utc_offset("Dublin", datetime(2026, 7, 1, tzinfo=UTC)) == timedelta(hours=1)
    assert fake.utc_offset("Dublin", datetime(2026, 12, 1, tzinfo=UTC)) == timedelta(0)
    assert fake.classify("Dublin", datetime(2026, 10, 25, 1, 30)) is LocalTimeKind.FOLD


@pytest.mark.parametrize(
    "text", ["", "EET", "EET-2EEST,M3.5.0", "123", "EET-2EEST,M13.5.0,M10.5.0"]
)
def test_malformed_posix_strings(text: str) -> None:
    with pytest.raises((TimeZoneError, ValueError)):
        zone = parse_posix_tz("Bad", text)
        zone.offset_at(datetime(2026, 6, 1, tzinfo=UTC))
