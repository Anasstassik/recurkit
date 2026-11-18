from datetime import UTC, date, datetime

import pytest

from recurkit import Rule
from recurkit.expand import after, before, between, is_occurrence

WEEKLY = Rule.parse("FREQ=WEEKLY;BYDAY=MO,TH", dtstart=datetime(2026, 11, 16, 10))


def test_between_includes_both_bounds_by_default() -> None:
    window = list(between(WEEKLY, datetime(2026, 11, 19, 10), datetime(2026, 11, 26, 10)))
    assert window == [
        datetime(2026, 11, 19, 10),
        datetime(2026, 11, 23, 10),
        datetime(2026, 11, 26, 10),
    ]
    exclusive = list(
        between(WEEKLY, datetime(2026, 11, 19, 10), datetime(2026, 11, 26, 10), inclusive=False)
    )
    assert exclusive == [datetime(2026, 11, 23, 10)]


def test_after_is_strictly_after_unless_inclusive() -> None:
    assert after(WEEKLY, datetime(2026, 11, 19, 10)) == datetime(2026, 11, 23, 10)
    assert after(WEEKLY, datetime(2026, 11, 19, 10), inclusive=True) == datetime(2026, 11, 19, 10)
    assert after(WEEKLY, datetime(2020, 1, 1)) == datetime(2026, 11, 16, 10)
    finite = Rule.parse("FREQ=DAILY;COUNT=2", dtstart=datetime(2026, 1, 1, 9))
    assert after(finite, datetime(2026, 1, 2, 9)) is None
    assert before(WEEKLY, datetime(2026, 11, 23, 10)) == datetime(2026, 11, 19, 10)
    assert before(WEEKLY, datetime(2026, 11, 16, 10)) is None
    assert is_occurrence(WEEKLY, datetime(2026, 11, 30, 10))
    assert not is_occurrence(WEEKLY, datetime(2026, 11, 30, 11))


def test_empty_and_reversed_windows() -> None:
    assert list(between(WEEKLY, datetime(2026, 11, 17), datetime(2026, 11, 18, 23))) == []
    assert list(between(WEEKLY, datetime(2026, 1, 1), datetime(2026, 11, 15))) == []
    with pytest.raises(ValueError, match="before its start"):
        list(between(WEEKLY, datetime(2026, 12, 1), datetime(2026, 11, 1)))


def test_bounds_are_coerced_to_the_rule_value_type() -> None:
    assert list(between(WEEKLY, date(2026, 11, 20), date(2026, 11, 24))) == [
        datetime(2026, 11, 23, 10)
    ]
    all_day = Rule.parse("FREQ=DAILY", dtstart=date(2026, 1, 1))
    assert after(all_day, datetime(2026, 1, 1, 15)) == date(2026, 1, 2)
    with pytest.raises(TypeError, match="naive"):
        after(WEEKLY, datetime(2026, 11, 16, tzinfo=UTC))
