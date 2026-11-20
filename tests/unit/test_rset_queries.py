from datetime import UTC, date, datetime, timedelta

from recurkit import RecurrenceSet, Rule
from recurkit.timezones import FakeProvider

FAKE = FakeProvider()
EE = "Fake/EasternEurope"


def _wall(value: object) -> datetime:
    return value.replace(tzinfo=None)  # type: ignore[attr-defined, no-any-return]


def test_between_merges_rdates_and_skips_exdates_in_window() -> None:
    rule = Rule.parse("FREQ=WEEKLY;BYDAY=MO,TH", dtstart=datetime(2026, 11, 16, 10), tzid=EE)
    rset = RecurrenceSet(
        rule,
        rdates=[datetime(2026, 11, 21, 12), datetime(2030, 1, 1, 9)],
        exdates=[datetime(2026, 11, 23, 10)],
        provider=FAKE,
    )
    window = [
        _wall(v) for v in rset.between(datetime(2026, 11, 19, 10), datetime(2026, 11, 30, 10))
    ]
    assert window == [
        datetime(2026, 11, 19, 10),
        datetime(2026, 11, 21, 12),
        datetime(2026, 11, 26, 10),
        datetime(2026, 11, 30, 10),
    ]
    exclusive = rset.between(
        datetime(2026, 11, 19, 10), datetime(2026, 11, 30, 10), inclusive=False
    )
    assert len(list(exclusive)) == 2
    far = list(rset.between(datetime(2029, 12, 31), datetime(2030, 1, 1, 23)))
    assert [_wall(v) for v in far] == [datetime(2029, 12, 31, 10), datetime(2030, 1, 1, 9)]


def test_after_and_before_across_a_dst_switch() -> None:
    rule = Rule.parse("FREQ=DAILY", dtstart=datetime(2026, 10, 20, 3, 30), tzid=EE)
    rset = RecurrenceSet(rule, provider=FAKE)
    first_fold = rset.after(datetime(2026, 10, 25, 0, 0, tzinfo=UTC))
    assert first_fold is not None and _wall(first_fold) == datetime(2026, 10, 25, 3, 30)
    # Second 03:30 of 25.10 (01:30 UTC) is not an instance: the next one is on 26.10.
    following = rset.after(datetime(2026, 10, 25, 1, 0, tzinfo=UTC))
    assert following is not None and _wall(following) == datetime(2026, 10, 26, 3, 30)
    previous = rset.before(datetime(2026, 10, 22, 3, 30))
    assert previous is not None and _wall(previous) == datetime(2026, 10, 21, 3, 30)
    assert rset.before(datetime(2026, 10, 20, 3, 30)) is None
    assert rset.after(datetime(2026, 10, 22, 3, 30), inclusive=True) == rset.coerce(
        datetime(2026, 10, 22, 3, 30)
    )


def test_bounds_of_every_kind_are_coerced() -> None:
    floating = RecurrenceSet(Rule.parse("FREQ=DAILY;COUNT=5", dtstart=datetime(2026, 1, 1, 9)))
    assert list(floating.between(date(2026, 1, 2), date(2026, 1, 3))) == [datetime(2026, 1, 2, 9)]
    all_day = RecurrenceSet(Rule.parse("FREQ=DAILY;COUNT=5", dtstart=date(2026, 1, 1)))
    assert all_day.after(datetime(2026, 1, 1, 18)) == date(2026, 1, 2)
    utc = RecurrenceSet(Rule.parse("FREQ=DAILY", dtstart=datetime(2026, 1, 1, 9, tzinfo=UTC)))
    assert utc.after(datetime(2026, 1, 1, 9, tzinfo=UTC)) == datetime(2026, 1, 2, 9, tzinfo=UTC)
    zoned = RecurrenceSet(
        Rule.parse("FREQ=DAILY", dtstart=datetime(2026, 1, 1, 9), tzid=EE), provider=FAKE
    )
    hit = zoned.after(date(2026, 1, 3))
    assert hit is not None and hit.utcoffset() == timedelta(hours=2)  # type: ignore[union-attr]
    assert _wall(hit) == datetime(2026, 1, 3, 9)
