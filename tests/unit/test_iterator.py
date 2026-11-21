from datetime import UTC, date, datetime
from itertools import islice

from recurkit import Rule
from recurkit.expand import Occurrence, occurrences


def _dates(text: str, dtstart: datetime | date, **kwargs: object) -> list[Occurrence]:
    return list(occurrences(Rule.parse(text, dtstart=dtstart), **kwargs))  # type: ignore[arg-type]


def test_design_document_example_second_tuesdays() -> None:
    result = _dates("FREQ=MONTHLY;BYDAY=2TU;COUNT=6", datetime(2026, 1, 6, 10))
    assert result == [
        datetime(2026, 1, 13, 10),
        datetime(2026, 2, 10, 10),
        datetime(2026, 3, 10, 10),
        datetime(2026, 4, 14, 10),
        datetime(2026, 5, 12, 10),
        datetime(2026, 6, 9, 10),
    ]


def test_rrule_12_unsynchronized_dtstart_is_not_added() -> None:
    first = _dates("FREQ=MONTHLY;BYDAY=2TU;COUNT=1", datetime(2026, 1, 6, 10))
    assert first == [datetime(2026, 1, 13, 10)]
    synced = _dates("FREQ=WEEKLY;COUNT=2", datetime(2026, 1, 6, 10))
    assert synced == [datetime(2026, 1, 6, 10), datetime(2026, 1, 13, 10)]


def test_rrule_11_until_is_inclusive() -> None:
    result = _dates("FREQ=DAILY;UNTIL=20260103T090000", datetime(2026, 1, 1, 9))
    assert result[-1] == datetime(2026, 1, 3, 9)
    assert len(result) == 3
    before = _dates("FREQ=DAILY;UNTIL=20260103T085959", datetime(2026, 1, 1, 9))
    assert before[-1] == datetime(2026, 1, 2, 9)
    utc = _dates("FREQ=DAILY;UNTIL=20260102T090000Z", datetime(2026, 1, 1, 9, tzinfo=UTC))
    assert utc == [datetime(2026, 1, 1, 9, tzinfo=UTC), datetime(2026, 1, 2, 9, tzinfo=UTC)]
    assert _dates("FREQ=DAILY;UNTIL=20261231", date(2026, 12, 30)) == [
        date(2026, 12, 30),
        date(2026, 12, 31),
    ]


def test_rrule_16_invalid_dates_are_not_counted() -> None:
    result = _dates("FREQ=MONTHLY;COUNT=5", datetime(2026, 1, 31, 8))
    assert [d.month for d in result] == [1, 3, 5, 7, 8]  # type: ignore[union-attr]
    leap = _dates("FREQ=YEARLY;COUNT=3", datetime(2024, 2, 29))
    assert [d.year for d in leap] == [2024, 2028, 2032]  # type: ignore[union-attr]


def test_infinite_rule_is_lazy() -> None:
    rule = Rule.parse("FREQ=DAILY;INTERVAL=7", dtstart=datetime(2026, 1, 1, 12))
    first = list(islice(occurrences(rule), 3))
    assert first == [datetime(2026, 1, 1, 12), datetime(2026, 1, 8, 12), datetime(2026, 1, 15, 12)]
    assert next(occurrences(Rule.parse("FREQ=YEARLY", dtstart=datetime(9999, 1, 1)))) == datetime(
        9999, 1, 1
    )


def test_is_valid_rejections_are_not_counted_in_count() -> None:
    def no_sundays(value: Occurrence) -> bool:
        return value.weekday() != 6

    result = _dates("FREQ=DAILY;COUNT=7", datetime(2026, 11, 16, 9), is_valid=no_sundays)
    assert len(result) == 7
    assert result[-1] == datetime(2026, 11, 23, 9)


def test_rrule_17_bysetpos_applies_before_count() -> None:
    result = _dates(
        "FREQ=MONTHLY;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=-1;COUNT=3", datetime(2026, 1, 1, 17)
    )
    assert result == [
        datetime(2026, 1, 30, 17),
        datetime(2026, 2, 27, 17),
        datetime(2026, 3, 31, 17),
    ]
