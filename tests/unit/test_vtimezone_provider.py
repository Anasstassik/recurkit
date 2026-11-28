from datetime import UTC, datetime, timedelta

import pytest

from recurkit import RecurrenceSet, Rule, TimeZoneError, parse_ics
from recurkit.ical import VTimezoneProvider
from recurkit.timezones import ZoneInfoProvider
from tests.conftest import vtimezone_provider
from tests.unit.test_ical_vtimezone import HEADER, NEW_YORK_1967

ZONES = vtimezone_provider()
HOUR = timedelta(hours=1)


def test_tzc_05_transitions_follow_the_observance_rules_and_until() -> None:
    assert ZONES.transitions("America/New_York", datetime(2009, 1, 1, tzinfo=UTC))[-2:] == [
        (datetime(2008, 3, 9, 7, tzinfo=UTC), -4 * HOUR),
        (datetime(2008, 11, 2, 6, tzinfo=UTC), -5 * HOUR),
    ]
    old = VTimezoneProvider(parse_ics(HEADER + NEW_YORK_1967 + "END:VCALENDAR\n").timezones)
    changes = old.transitions("America/New_York", datetime(2030, 1, 1, tzinfo=UTC))
    assert changes[0] == (datetime(1967, 4, 30, 7, tzinfo=UTC), -4 * HOUR)
    assert (datetime(1975, 2, 23, 7, tzinfo=UTC), -4 * HOUR) in changes
    assert changes[-1] == (datetime(2006, 10, 29, 6, tzinfo=UTC), -5 * HOUR)
    assert old.utc_offset("America/New_York", datetime(2020, 7, 1, tzinfo=UTC)) == -5 * HOUR


def test_offset_before_the_first_onset_is_its_tzoffsetfrom() -> None:
    assert ZONES.utc_offset("Asia/Kolkata", datetime(1940, 1, 1, tzinfo=UTC)) == 6.5 * HOUR
    assert ZONES.utc_offset("Asia/Kolkata", datetime(1950, 1, 1, tzinfo=UTC)) == 5.5 * HOUR
    assert ZONES.utc_offset("Australia/Sydney", datetime(2008, 1, 1, tzinfo=UTC)) == 11 * HOUR


def test_far_future_offsets_keep_the_rules_and_reach_year_9999() -> None:
    zoneinfo = ZoneInfoProvider()
    for year in (2100, 5000, 9998):
        for month in (1, 4, 7, 10):
            instant = datetime(year, month, 15, 12, tzinfo=UTC)
            for tzid in ("Europe/Kyiv", "America/New_York", "Australia/Lord_Howe"):
                assert ZONES.utc_offset(tzid, instant) == zoneinfo.utc_offset(tzid, instant)
    assert ZONES.to_local("Europe/Kyiv", datetime(9999, 12, 31, 20, tzinfo=UTC)).year == 9999


def test_tz_03_and_tz_04_a_zoned_series_runs_on_the_vtimezone_provider() -> None:
    rule = Rule.parse(
        "FREQ=DAILY;COUNT=3", dtstart=datetime(2026, 3, 28, 3, 30), tzid="Europe/Kyiv"
    )
    values = list(RecurrenceSet(rule, provider=ZONES))
    assert [v.replace(tzinfo=None) for v in values] == [
        datetime(2026, 3, 28, 3, 30),
        datetime(2026, 3, 30, 3, 30),
        datetime(2026, 3, 31, 3, 30),
    ]
    assert [v.utcoffset() for v in values] == [2 * HOUR, 3 * HOUR, 3 * HOUR]
    with pytest.raises(TimeZoneError, match="unknown time zone"):
        RecurrenceSet(
            Rule.parse("FREQ=DAILY", dtstart=datetime(2026, 1, 1), tzid="Europe/Berlin"),
            provider=ZONES,
        )
