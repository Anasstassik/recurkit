from datetime import UTC, datetime, timedelta, timezone

import pytest

from recurkit import RecurrenceSet, Rule, TimeZoneError
from recurkit.timezones import FakeProvider

FAKE = FakeProvider()
EE = "Fake/EasternEurope"  # 2026-03-29 03:00 -> 04:00, 2026-10-25 04:00 -> 03:00


def _rset(text: str, dtstart: datetime, **kwargs: object) -> RecurrenceSet:
    rule = Rule.parse(text, dtstart=dtstart, tzid=EE)
    return RecurrenceSet(rule, provider=FAKE, **kwargs)  # type: ignore[arg-type]


def _walls(values: list[object]) -> list[datetime]:
    return [v.replace(tzinfo=None) for v in values]  # type: ignore[attr-defined]


def test_tz_03_rule_instance_in_gap_is_dropped_and_not_counted() -> None:
    values = list(_rset("FREQ=DAILY;COUNT=3", datetime(2026, 3, 28, 3, 30)))
    assert _walls(values) == [
        datetime(2026, 3, 28, 3, 30),
        datetime(2026, 3, 30, 3, 30),  # 29.03 03:30 does not exist
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
    # DTSTART 03:30 on the gap day is moved to 04:30 and still counts as the first instance.
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
    # 2026-11-16 10:00 at +02:00 is 08:00 UTC: an EXDATE given in UTC removes it.
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
    assert len(list(other)) == 1  # 10:00 UTC is 12:00 local: a different instant
    aware_rdate = _rset(
        "FREQ=DAILY;COUNT=1",
        datetime(2026, 11, 16, 10),
        rdates=[datetime(2026, 11, 16, 9, tzinfo=timezone(timedelta(hours=1)))],
    )
    assert aware_rdate.rdates[0].utcoffset() == timedelta(hours=2)  # type: ignore[union-attr]
    assert _walls(list(aware_rdate)) == [datetime(2026, 11, 16, 10)]  # same instant: one value


def test_utc_until_and_unknown_zone() -> None:
    rule = Rule.parse(
        "FREQ=DAILY;UNTIL=20261118T080000Z", dtstart=datetime(2026, 11, 16, 10), tzid=EE
    )
    assert len(list(RecurrenceSet(rule, provider=FAKE))) == 3  # 18.11 10:00 local == 08:00 UTC
    with pytest.raises(TimeZoneError):
        RecurrenceSet(Rule.parse("FREQ=DAILY", dtstart=datetime(2026, 1, 1), tzid="Mars/Olympus"))
    kyiv = RecurrenceSet(
        Rule.parse("FREQ=DAILY;COUNT=1", dtstart=datetime(2026, 7, 1, 9), tzid="Europe/Kyiv")
    )
    assert next(iter(kyiv)).utcoffset() == timedelta(hours=3)  # type: ignore[union-attr]
