from datetime import date, datetime

import pytest

from recurkit import Rule
from recurkit.expand import after, between, plan_for
from recurkit.expand.jump import (
    can_jump,
    next_allowed_month_start,
    next_productive_step,
    occurrences_from,
)
from recurkit.expand.periods import period_at


def test_query_far_from_dtstart_starts_at_the_window() -> None:
    rule = Rule.parse("FREQ=WEEKLY;INTERVAL=2;BYDAY=TU,TH;WKST=SU", dtstart=datetime(1997, 9, 2, 9))
    window = list(between(rule, datetime(2496, 1, 1), datetime(2496, 1, 31)))
    linear = [
        value
        for value in occurrences_from(rule, datetime(1997, 9, 2, 9), until=datetime(2496, 1, 31))
        if value >= datetime(2496, 1, 1)
    ]
    assert window == linear
    assert all(value.weekday() in (1, 3) for value in window)  # type: ignore[union-attr]
    first = next(occurrences_from(rule, datetime(2496, 1, 1)))
    assert first <= window[0]  # type: ignore[operator]


def test_by_month_limit_skips_empty_periods_arithmetically() -> None:
    plan = plan_for(Rule.parse("FREQ=DAILY;BYMONTH=12", dtstart=datetime(2026, 1, 1, 8)))
    step = next_productive_step(plan, 0)
    assert step is not None
    period = period_at(plan, step)
    assert period is not None and period.first == date(2026, 12, 1)
    assert next_allowed_month_start(date(2026, 12, 31), frozenset({12})) == date(2027, 12, 1)
    assert next_allowed_month_start(date(9999, 12, 1), frozenset({1})) is None
    monthly = plan_for(
        Rule.parse("FREQ=MONTHLY;INTERVAL=12;BYMONTH=2", dtstart=datetime(2026, 3, 1))
    )
    assert next_productive_step(monthly, 0) is None  # March + 12k months is never February
    rule = Rule.parse("FREQ=DAILY;BYMONTH=2;BYMONTHDAY=29", dtstart=datetime(2026, 1, 1, 8))
    assert after(rule, datetime(2026, 1, 1)) == datetime(2028, 2, 29, 8)


def test_count_falls_back_to_counting_from_dtstart() -> None:
    counted = Rule.parse("FREQ=DAILY;COUNT=5", dtstart=datetime(2026, 1, 1, 9))
    assert not can_jump(counted)
    assert list(between(counted, datetime(2026, 1, 4), datetime(2026, 12, 31))) == [
        datetime(2026, 1, 4, 9),
        datetime(2026, 1, 5, 9),
    ]
    assert after(counted, datetime(2026, 1, 5, 9)) is None
    with pytest.raises(ValueError, match="COUNT"):
        next(occurrences_from(counted, datetime(2026, 1, 3)))
