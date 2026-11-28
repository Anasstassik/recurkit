from datetime import UTC, date, datetime, timedelta

import pytest

from recurkit import RecurrenceSet, Rule, TimeZoneError
from recurkit.recurrence_set import ValueKind
from recurkit.timezones import FakeProvider, ZoneFrame, ZoneInfoProvider

BERLIN = ZoneFrame(ZoneInfoProvider(), "Europe/Berlin")
EE = ZoneFrame(FakeProvider(), "Fake/EasternEurope")


def test_frame_checks_its_zone_when_built() -> None:
    with pytest.raises(TimeZoneError):
        ZoneFrame(FakeProvider(), "Fake/Nowhere")


def test_place_gives_a_wall_time_and_an_instant_the_zone_offset() -> None:
    summer = BERLIN.place(datetime(2026, 7, 1, 9))
    assert summer.utcoffset() == timedelta(hours=2)
    assert summer.tzname() == "Europe/Berlin"
    moved = BERLIN.place(datetime(2026, 1, 1, 8, tzinfo=UTC))
    assert moved.replace(tzinfo=None) == datetime(2026, 1, 1, 9)
    assert moved.utcoffset() == timedelta(hours=1)


def test_to_local_and_exists_use_the_zone() -> None:
    instant = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert BERLIN.to_local(instant) == datetime(2026, 10, 25, 2, 30)
    assert not EE.exists(datetime(2026, 3, 29, 3, 30))
    assert EE.exists(datetime(2026, 3, 29, 4, 30))


def test_local_window_across_a_dst_fold_keeps_a_later_wall_time_of_an_earlier_instant() -> None:
    high = datetime(2026, 10, 25, 1, 10, tzinfo=UTC)
    summer = BERLIN.place(datetime(2026, 10, 25, 2, 30))
    assert summer <= high
    assert summer.replace(tzinfo=None) > BERLIN.to_local(high)
    low_local, high_local = BERLIN.local_window(datetime(2026, 10, 24, 22, tzinfo=UTC), high)
    assert low_local == datetime(2026, 10, 24, 23, 0)
    assert high_local == datetime(2026, 10, 25, 3, 10)
    assert isinstance(high_local, datetime) and summer.replace(tzinfo=None) <= high_local


def test_local_window_widens_only_by_the_offset_change_near_a_bound() -> None:
    summer = datetime(2026, 7, 1, 12, tzinfo=UTC)
    assert BERLIN.local_window(summer, summer) == (
        datetime(2026, 7, 1, 14),
        datetime(2026, 7, 1, 14),
    )
    spring = datetime(2026, 3, 29, 0, 30, tzinfo=UTC)
    assert BERLIN.margin(spring, -1) == timedelta(0)
    assert BERLIN.margin(spring, 1) == timedelta(0)
    autumn = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert BERLIN.margin(autumn, -1) == timedelta(hours=1)
    assert BERLIN.margin(autumn + timedelta(hours=1), 1) == timedelta(hours=1)


def test_local_window_passes_dates_and_open_ends_through() -> None:
    assert BERLIN.local_window(None, None) == (None, None)
    assert BERLIN.local_window(date(2026, 1, 1), None) == (date(2026, 1, 1), None)


@pytest.mark.parametrize(
    ("dtstart", "tzid", "kind"),
    [
        (date(2026, 1, 1), None, ValueKind.ALL_DAY),
        (datetime(2026, 1, 1, 9), None, ValueKind.FLOATING),
        (datetime(2026, 1, 1, 9, tzinfo=UTC), None, ValueKind.UTC),
        (datetime(2026, 1, 1, 9), "Europe/Berlin", ValueKind.ZONED),
    ],
)
def test_set_decides_its_kind_and_frame_once(
    dtstart: date, tzid: str | None, kind: ValueKind
) -> None:
    rset = RecurrenceSet(Rule.parse("FREQ=DAILY;COUNT=2", dtstart=dtstart, tzid=tzid))
    assert rset.kind is kind
    assert (rset.frame is not None) == (kind is ValueKind.ZONED)
    assert rset.tzid == tzid
    assert (rset.provider is None) == (tzid is None)


@pytest.mark.parametrize(
    ("kind", "value", "accepted"),
    [
        (ValueKind.ALL_DAY, date(2026, 1, 1), True),
        (ValueKind.ALL_DAY, datetime(2026, 1, 1), False),
        (ValueKind.FLOATING, datetime(2026, 1, 1), True),
        (ValueKind.FLOATING, datetime(2026, 1, 1, tzinfo=UTC), False),
        (ValueKind.FLOATING, date(2026, 1, 1), False),
        (ValueKind.UTC, datetime(2026, 1, 1, tzinfo=UTC), True),
        (ValueKind.UTC, datetime(2026, 1, 1), False),
        (ValueKind.ZONED, datetime(2026, 1, 1), True),
        (ValueKind.ZONED, datetime(2026, 1, 1, tzinfo=UTC), True),
        (ValueKind.ZONED, date(2026, 1, 1), False),
    ],
)
def test_kind_accepts_only_values_of_its_kind(kind: ValueKind, value: date, accepted: bool) -> None:
    assert kind.accepts(value) is accepted
