from datetime import UTC, datetime, timedelta, timezone

import pytest

from recurkit import RecurrenceSet, Rule, TimeZoneError
from recurkit.timezones import FakeProvider

FAKE = FakeProvider()
EE = "Fake/EasternEurope"


def _rset(text: str, dtstart: datetime, **kwargs: object) -> RecurrenceSet:
    rule = Rule.parse(text, dtstart=dtstart, tzid=EE)
    return RecurrenceSet(rule, provider=FAKE, **kwargs)  # type: ignore[arg-type]


def _walls(values: list[object]) -> list[datetime]:
    return [v.replace(tzinfo=None) for v in values]  # type: ignore[attr-defined]


def test_tz_03_rule_instance_in_gap_is_dropped_and_not_counted() -> None:
    values = list(_rset("FREQ=DAILY;COUNT=3", datetime(2026, 3, 28, 3, 30)))
    assert _walls(values) == [
        datetime(2026, 3, 28, 3, 30),
        datetime(2026, 3, 30, 3, 30),
        datetime(2026, 3, 31, 3, 30),
    ]
    assert values[0].utcoffset() == timedelta(hours=2)  # type: ignore[union-attr]
    assert values[1].utcoffset() == timedelta(hours=3)  # type: ignore[union-attr]


def test_tz_02_explicit_dtstart_and_rdate_in_gap_are_shifted() -> None:
    values = list(
        _rset(
            "FREQ=YEARLY;COUNT=2",
            datetime(2026, 3, 29, 3, 30),
            rdates=[datetime(2027, 3, 28, 3, 15)],
        )
    )
    assert _walls(values) == [
        datetime(2026, 3, 29, 4, 30),
        datetime(2027, 3, 28, 4, 15),
        datetime(2027, 3, 29, 3, 30),
    ]


def test_tz_01_instance_in_fold_is_the_first_occurrence() -> None:
    values = list(_rset("FREQ=DAILY;COUNT=2", datetime(2026, 10, 24, 3, 30)))
    fold = values[1]
    assert fold.replace(tzinfo=None) == datetime(2026, 10, 25, 3, 30)  # type: ignore[call-arg]
    assert fold.astimezone(UTC) == datetime(2026, 10, 25, 0, 30, tzinfo=UTC)  # type: ignore[union-attr]


def test_exdate_is_compared_as_utc_instant() -> None:
    rset = _rset(
        "FREQ=DAILY;COUNT=3",
        datetime(2026, 11, 16, 10),
        exdates=[datetime(2026, 11, 16, 8, tzinfo=UTC), datetime(2026, 11, 17, 10)],
    )
    assert _walls(list(rset)) == [datetime(2026, 11, 18, 10)]
    other = _rset(
        "FREQ=DAILY;COUNT=1",
        datetime(2026, 11, 16, 10),
        exdates=[datetime(2026, 11, 16, 10, tzinfo=UTC)],
    )
    assert len(list(other)) == 1
    aware_rdate = _rset(
        "FREQ=DAILY;COUNT=1",
        datetime(2026, 11, 16, 10),
        rdates=[datetime(2026, 11, 16, 9, tzinfo=timezone(timedelta(hours=1)))],
    )
    assert aware_rdate.rdates[0].utcoffset() == timedelta(hours=2)  # type: ignore[union-attr]
    assert _walls(list(aware_rdate)) == [datetime(2026, 11, 16, 10)]


def test_utc_until_and_unknown_zone() -> None:
    rule = Rule.parse(
        "FREQ=DAILY;UNTIL=20261118T080000Z", dtstart=datetime(2026, 11, 16, 10), tzid=EE
    )
    assert len(list(RecurrenceSet(rule, provider=FAKE))) == 3
    with pytest.raises(TimeZoneError):
        RecurrenceSet(Rule.parse("FREQ=DAILY", dtstart=datetime(2026, 1, 1), tzid="Mars/Olympus"))
    kyiv = RecurrenceSet(
        Rule.parse("FREQ=DAILY;COUNT=1", dtstart=datetime(2026, 7, 1, 9), tzid="Europe/Kyiv")
    )
    assert next(iter(kyiv)).utcoffset() == timedelta(hours=3)  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("dtstart", "expected"),
    [
        (datetime(9999, 12, 30, 9), ["9999-12-30T09:00:00+02:00", "9999-12-31T09:00:00+02:00"]),
        (datetime(1, 1, 1, 9), ["0001-01-01T09:00:00+02:00", "0001-01-02T09:00:00+02:00"]),
    ],
    ids=["last-days", "first-days"],
)
def test_h4_zoned_series_at_the_ends_of_the_calendar(
    dtstart: datetime, expected: list[str]
) -> None:
    rule = Rule.parse("FREQ=DAILY;COUNT=2", dtstart=dtstart, tzid=EE)
    assert [value.isoformat() for value in RecurrenceSet(rule, provider=FAKE)] == expected


def test_d18_query_bounds_at_the_ends_of_the_calendar() -> None:
    rset = _rset("FREQ=DAILY;COUNT=3", datetime(2026, 1, 1, 9))
    first, last = datetime(1, 1, 1, tzinfo=UTC), datetime(9999, 12, 31, 21, 59, tzinfo=UTC)
    values = list(rset)
    assert rset.after(first) == values[0]
    assert rset.before(last) == values[-1]
    assert list(rset.between(first, last)) == values
    assert list(rset.between(first, datetime(2026, 1, 1, 7, tzinfo=UTC))) == values[:1]


def test_d18_local_time_without_an_instant_is_a_time_zone_error() -> None:
    with pytest.raises(TimeZoneError, match="years 1 to 9999"):
        FAKE.localize(EE, datetime(1, 1, 1, 0, 30))
    with pytest.raises(TimeZoneError, match="years 1 to 9999"):
        _rset("FREQ=DAILY", datetime(2026, 1, 1, 9)).after(datetime(1, 1, 1))
    with pytest.raises(TimeZoneError, match="years 1 to 9999"):
        _rset("FREQ=DAILY", datetime(2026, 1, 1, 9)).before(datetime.max.replace(tzinfo=UTC))
    new_york = Rule.parse(
        "FREQ=DAILY", dtstart=datetime(9999, 12, 31, 23, 30), tzid="America/New_York"
    )
    with pytest.raises(TimeZoneError, match="years 1 to 9999"):
        list(RecurrenceSet(new_york))
