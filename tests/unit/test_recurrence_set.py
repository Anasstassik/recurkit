from datetime import UTC, date, datetime
from itertools import islice

import pytest

from recurkit import Rule
from recurkit.recurrence_set import RecurrenceSet, merge_unique

WEEKLY = Rule.parse("FREQ=WEEKLY;COUNT=4", dtstart=datetime(2026, 11, 16, 10))


def test_rset_01_rule_plus_rdate_minus_exdate() -> None:
    rset = RecurrenceSet(
        WEEKLY,
        rdates=[datetime(2026, 11, 20, 15), datetime(2026, 11, 17, 9)],
        exdates=[datetime(2026, 11, 23, 10)],
    )
    assert list(rset) == [
        datetime(2026, 11, 16, 10),
        datetime(2026, 11, 17, 9),
        datetime(2026, 11, 20, 15),
        datetime(2026, 11, 30, 10),
        datetime(2026, 12, 7, 10),
    ]


def test_rset_02_exdate_wins_over_rdate_and_rule() -> None:
    clash = datetime(2026, 11, 18, 12)
    rset = RecurrenceSet(WEEKLY, rdates=[clash], exdates=[clash, datetime(2026, 11, 16, 10)])
    assert clash not in list(rset)
    assert next(iter(rset)) == datetime(2026, 11, 23, 10)
    # An EXDATE that matches nothing changes nothing.
    assert len(list(RecurrenceSet(WEEKLY, exdates=[datetime(2026, 11, 23, 11)]))) == 4


def test_rset_03_duplicates_from_rule_and_rdate_appear_once() -> None:
    rset = RecurrenceSet(WEEKLY, rdates=[datetime(2026, 11, 23, 10), datetime(2026, 11, 23, 10)])
    values = list(rset)
    assert values.count(datetime(2026, 11, 23, 10)) == 1
    assert len(values) == 4
    assert list(merge_unique([1, 3, 5], [1, 2, 3], [])) == [1, 2, 3, 5]  # type: ignore[list-item]


def test_unsynchronized_dtstart_is_not_force_added() -> None:
    # Decision D-03: DTSTART 06.01 (not a second Tuesday) is not in the set.
    rule = Rule.parse("FREQ=MONTHLY;BYDAY=2TU;COUNT=6", dtstart=datetime(2026, 1, 6, 10))
    values = list(RecurrenceSet(rule))
    assert datetime(2026, 1, 6, 10) not in values
    assert len(values) == 6
    infinite = RecurrenceSet(Rule.parse("FREQ=DAILY", dtstart=datetime(2026, 1, 1, 8)))
    assert len(list(islice(infinite, 1000))) == 1000
    assert "FREQ=DAILY" in repr(infinite)


def test_explicit_values_must_match_dtstart_kind() -> None:
    with pytest.raises(TypeError):
        RecurrenceSet(WEEKLY, rdates=[date(2026, 11, 20)])
    with pytest.raises(TypeError):
        RecurrenceSet(WEEKLY, exdates=[datetime(2026, 11, 20, tzinfo=UTC)])
